import json
import threading
import time
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Tuple

import depthai as dai
import numpy as np

from utils.board_config import ImuMounting
from utils.imu_calibration import POSES, ImuCalibration, calibrate, orientation_error
from utils.device_info import read_device_info

IMU_RATE_HZ = 100
GRAPH_DECIMATION = 4  # every 4th packet -> 25 Hz to the frontend graph
GRAPH_WINDOW = 250  # graph samples kept (10 s)
SETTLE = timedelta(
    seconds=0.5
)  # ignore samples right after Capture, while the hand lets go
MAX_ACCEL_STD = 0.25  # m/s^2; above this the device moved during the capture
MIN_SAMPLES = 50


class ImuCalibrator(dai.node.ThreadedHostNode):
    """Six-pose capture state machine; the frontend drives it through `state()` and `action()`.

    Services call in from the RemoteConnection thread, so all state is guarded by one lock.
    """

    def __init__(self) -> None:
        super().__init__()
        self.imu_input = self.createInput()
        self._lock = threading.Lock()
        self._recent: deque = deque(maxlen=IMU_RATE_HZ // 2)
        self._graph: deque = deque(maxlen=GRAPH_WINDOW)
        self._packets = 0
        self._session = int(
            time.time()
        )  # lets the frontend tell a backend restart from a stale reply
        self._reset()

    def build(
        self,
        imu_out: dai.Node.Output,
        device: dai.Device,
        mounting: ImuMounting,
        output_dir: Path,
        capture_seconds: float,
    ) -> "ImuCalibrator":
        imu_out.link(self.imu_input)
        self._device = device
        self._mounting = mounting
        self._output_dir = output_dir
        self._capture_duration = timedelta(seconds=capture_seconds)
        self._device_info = read_device_info(device, mounting)
        return self

    def _reset(self) -> None:
        self._accel_means: List[np.ndarray] = []
        self._gyro_means: List[np.ndarray] = []
        self._samples: List[Tuple[float, ...]] = []
        self._capture_start: Optional[timedelta] = (
            None  # dai.Clock time, set while capturing
        )
        self._message = ""
        self._result: Optional[ImuCalibration] = None
        self._flashed = False

    def run(self) -> None:
        while self.isRunning():
            imu_data = self.imu_input.get()
            with self._lock:
                for packet in imu_data.packets:
                    self._ingest(packet)
                if (
                    self._capture_start is not None
                    and dai.Clock.now() >= self._capture_start + self._capture_duration
                ):
                    self._finish_capture()

    def _ingest(self, packet: dai.IMUPacket) -> None:
        a, g, m = packet.acceleroMeter, packet.gyroscope, packet.magneticField
        self._recent.append((a.x, a.y, a.z))
        if self._capturing(a.getTimestamp()):
            self._samples.append((a.x, a.y, a.z, g.x, g.y, g.z))
        self._packets += 1
        if self._packets % GRAPH_DECIMATION == 0:
            self._graph.append(
                {
                    "seq": self._packets,
                    "accel": _vec(a),
                    "gyro": _vec(g),
                    "mag": _vec(m),
                }
            )

    def _capturing(self, timestamp: timedelta) -> bool:
        start = self._capture_start
        return start is not None and start <= timestamp < start + self._capture_duration

    def _imu_ready(self) -> bool:
        # The IMU can take a few seconds to start streaming after pipeline start (seen on RVC4).
        return len(self._recent) == self._recent.maxlen

    def state(self, since: int) -> dict:
        with self._lock:
            idx = min(len(self._accel_means), len(POSES) - 1)
            recent = np.asarray(self._recent) if self._imu_ready() else None
            orientation = None
            phase = self._phase()
            if recent is not None and self._accel_means and phase != "results":
                orientation = orientation_error(recent.mean(axis=0), self._accel_means)
            return {
                "session": self._session,
                "seq": self._packets,
                "phase": phase,
                "pose": {
                    "index": idx + 1,
                    "count": len(POSES),
                    "instruction": POSES[idx].instruction,
                },
                "progress": self._progress(),
                "imuReady": recent is not None,
                "still": recent is not None and _is_still(recent),
                "orientationError": orientation,
                "message": self._message,
                "messageOk": self._flashed,
                "samples": [s for s in self._graph if s["seq"] > since],
                "device": self._device_info,
                "result": self._result_json(),
            }

    def _phase(self) -> str:
        if self._result is not None:
            return "results"
        return "pose" if self._capture_start is None else "capturing"

    def action(self, name: str) -> dict:
        with self._lock:
            phase = self._phase()
            if name == "capture" and phase == "pose" and self._imu_ready():
                self._samples = []
                self._message = ""
                self._capture_start = dai.Clock.now() + SETTLE
            elif name == "back" and phase == "pose" and self._accel_means:
                self._accel_means.pop()
                self._gyro_means.pop()
                self._message = ""
            elif name == "redo":
                self._reset()
            elif (
                name == "flash"
                and phase == "results"
                and not self._result.problems
                and not self._flashed
            ):
                self._flash()
            else:
                return {"ok": False}
            return {"ok": True}

    def _progress(self) -> float:
        if self._capture_start is None:
            return 0.0
        elapsed = max(timedelta(0), dai.Clock.now() - self._capture_start)
        return min(1.0, elapsed / self._capture_duration)

    def _result_json(self) -> Optional[dict]:
        result = self._result
        if result is None:
            return None
        spec = self._mounting.spec_rotation
        return {
            **_calibration_dict(result),
            "specMatch": None
            if spec is None
            else bool(np.allclose(result.rotation, spec)),
            "flashed": self._flashed,
        }

    def _finish_capture(self) -> None:
        self._capture_start = None
        samples = np.asarray(self._samples)
        if len(samples) < MIN_SAMPLES:
            self._message = f"Only {len(samples)} IMU samples received. Capture again."
            return
        accel_mean = samples[:, :3].mean(axis=0)
        if not _is_still(samples[:, :3]):
            self._message = (
                "The device moved during the capture. Hold it still and capture again."
            )
            return
        if orientation_error(accel_mean, self._accel_means):
            self._message = "Capture rejected: wrong orientation. Match the photo and capture again."
            return
        self._accel_means.append(accel_mean)
        self._gyro_means.append(samples[:, 3:].mean(axis=0))
        if len(self._accel_means) == len(POSES):
            try:
                self._result = calibrate(
                    np.asarray(self._accel_means), np.asarray(self._gyro_means)
                )
            except np.linalg.LinAlgError:
                self._accel_means.pop()
                self._gyro_means.pop()
                self._message = (
                    "The fit failed on these poses. Capture the last pose again."
                )
                return
            self._save_report()

    def _save_report(self) -> None:
        self._output_dir.mkdir(parents=True, exist_ok=True)
        path = self._output_dir / f"imu_calibration_{datetime.now():%Y%m%d_%H%M%S}.json"
        report = {
            "mountingSource": self._mounting.source,
            "poseAccelerometerMeans": np.asarray(self._accel_means).tolist(),
            "poseGyroscopeMeans": np.asarray(self._gyro_means).tolist(),
            **_calibration_dict(self._result),
        }
        path.write_text(json.dumps(report, indent=2))
        print(f"Saved calibration report to {path}")

    def _flash(self) -> None:
        result, mounting = self._result, self._mounting
        try:
            calibration = self._device.readCalibration2()
            self._output_dir.mkdir(parents=True, exist_ok=True)
            backup = (
                self._output_dir
                / f"calibration_backup_{datetime.now():%Y%m%d_%H%M%S}.json"
            ).resolve()
            calibration.eepromToJsonFile(str(backup))
            calibration.setAccelerometerCalibration(result.accelerometer.tolist())
            calibration.setGyroscopeCalibration(result.gyroscope.tolist())
            calibration.setImuExtrinsics(
                mounting.socket,
                result.rotation.tolist(),
                mounting.translation_cm,
                mounting.spec_translation_cm,
            )
            self._device.flashCalibration(calibration)
        except RuntimeError as e:
            self._message = f"Flash failed: {e}"
            return
        self._flashed = True
        self._message = f"Flashed. Previous calibration saved to {backup}"
        # The flashed values become the "old" calibration the frontend compares against.
        self._device_info = read_device_info(self._device, mounting)
        print(self._message)


def _calibration_dict(result: ImuCalibration) -> dict:
    return {
        "rotation": result.rotation.tolist(),
        "accelerometer": result.accelerometer.tolist(),
        "gyroscope": result.gyroscope.tolist(),
        "poseTilts": result.pose_tilts.tolist(),
        "fitError": result.fit_error,
        "problems": result.problems,
    }


def _vec(v) -> List[float]:
    return [round(v.x, 4), round(v.y, 4), round(v.z, 4)]


def _is_still(accel: np.ndarray) -> bool:
    return bool(np.linalg.norm(accel.std(axis=0)) <= MAX_ACCEL_STD)
