import threading
from collections import deque
from datetime import timedelta
from typing import List, Optional, Tuple

import depthai as dai
import numpy as np

from utils.imu_calibration import POSES, ImuCalibration, calibrate, orientation_error

IMU_RATE_HZ = 100
GRAPH_DECIMATION = 4  # every 4th packet -> 25 Hz to the frontend graph
GRAPH_WINDOW = 250  # graph samples kept (10 s)
SETTLE = timedelta(
    seconds=0.5
)  # ignore samples right after Capture, while the hand lets go
MAX_ACCEL_STD = 0.25  # m/s^2; above this the device moved during the capture
MIN_SAMPLES = 50


class ImuCalibrator(dai.node.ThreadedHostNode):
    """Six-pose capture state machine; `Session` drives it through `state()` and `action()`.

    Services call in from the RemoteConnection thread, so all state is guarded by one lock.
    """

    def __init__(self) -> None:
        super().__init__()
        self.imu_input = self.createInput()
        self._lock = threading.Lock()
        self._recent: deque = deque(maxlen=IMU_RATE_HZ // 2)
        self._graph: deque = deque(maxlen=GRAPH_WINDOW)
        self._packets = 0
        self._reset()

    def build(self, imu_out: dai.Node.Output, capture_seconds: float) -> "ImuCalibrator":
        imu_out.link(self.imu_input)
        self._capture_duration = timedelta(seconds=capture_seconds)
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

    @property
    def result(self) -> Optional[ImuCalibration]:
        with self._lock:
            return self._result

    def recent_accel_mean(self) -> Optional[List[float]]:
        """RAW accelerometer mean of the last 0.5 s, or None unless the device was still."""
        with self._lock:
            recent = np.asarray(self._recent)
        if len(recent) < self._recent.maxlen or not _is_still(recent):
            return None
        return recent.mean(axis=0).tolist()

    def state(self, since: int) -> dict:
        with self._lock:
            idx = min(len(self._accel_means), len(POSES) - 1)
            recent = np.asarray(self._recent) if self._imu_ready() else None
            orientation = None
            phase = self._phase()
            if recent is not None and self._accel_means and phase != "results":
                orientation = orientation_error(recent.mean(axis=0), self._accel_means)
            return {
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
                "messageOk": False,  # only errors are reported here
                "samples": [s for s in self._graph if s["seq"] > since],
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
            else:
                return {"ok": False}
            return {"ok": True}

    def _progress(self) -> float:
        if self._capture_start is None:
            return 0.0
        elapsed = max(timedelta(0), dai.Clock.now() - self._capture_start)
        return min(1.0, elapsed / self._capture_duration)

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


def _vec(v) -> List[float]:
    return [round(v.x, 4), round(v.y, 4), round(v.z, 4)]


def _is_still(accel: np.ndarray) -> bool:
    return bool(np.linalg.norm(accel.std(axis=0)) <= MAX_ACCEL_STD)
