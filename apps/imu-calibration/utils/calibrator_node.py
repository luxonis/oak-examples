import json
import queue
import textwrap
import time
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import depthai as dai
import numpy as np

from utils.board_config import ImuMounting
from utils.calibration import POSES, ImuCalibration, calibrate, orientation_error

IMU_RATE_HZ = 100
UI_FPS = 15
SETTLE = timedelta(
    seconds=0.5
)  # ignore samples right after the key press, while the hand lets go
MAX_ACCEL_STD = 0.25  # m/s^2; above this the device moved during the capture
MIN_SAMPLES = 50

WIDTH, HEIGHT = 1280, 720
PHOTO_ORIGIN = (552, 88)  # photos in assets/poses are 704x528
FONT = cv2.FONT_HERSHEY_SIMPLEX
WHITE, GREY, GREEN, RED, PINK = (
    (240, 240, 245),
    (170, 170, 180),
    (90, 200, 90),
    (80, 80, 240),
    (120, 60, 255),
)
PHOTOS_DIR = Path(__file__).parent.parent / "assets" / "poses"

Line = Tuple[str, Tuple[int, int, int]]


class ImuCalibrator(dai.node.ThreadedHostNode):
    """Guides the user through the six poses, computes the calibration and flashes it on request.

    Keys arrive from the main thread through `keys` (the Visualizer's waitKey).
    """

    def __init__(self) -> None:
        super().__init__()
        self.imu_input = self.createInput()
        self.out = self.createOutput()
        self.keys: "queue.Queue[int]" = queue.Queue()
        self._photos = [
            cv2.imread(str(PHOTOS_DIR / f"{i}.jpg")) for i in range(1, len(POSES) + 1)
        ]
        if any(photo is None for photo in self._photos):
            raise FileNotFoundError(f"Pose photos missing in {PHOTOS_DIR}")
        self._recent: deque = deque(maxlen=IMU_RATE_HZ // 2)
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
            for imu_data in self.imu_input.tryGetAll():
                for packet in imu_data.packets:
                    a, g = packet.acceleroMeter, packet.gyroscope
                    self._recent.append((a.x, a.y, a.z))
                    if self._capturing(a.getTimestamp()):
                        self._samples.append((a.x, a.y, a.z, g.x, g.y, g.z))
            while not self.keys.empty():
                self._on_key(self.keys.get())
            if (
                self._capture_start is not None
                and dai.Clock.now() >= self._capture_start + self._capture_duration
            ):
                self._finish_capture()

            frame = dai.ImgFrame()
            frame.setCvFrame(self._render(), dai.ImgFrame.Type.NV12)
            frame.setTimestamp(dai.Clock.now())
            self.out.send(frame)
            time.sleep(1 / UI_FPS)

    def _capturing(self, timestamp: timedelta) -> bool:
        start = self._capture_start
        return start is not None and start <= timestamp < start + self._capture_duration

    def _on_key(self, key: int) -> None:
        if self._result is not None:
            if key == ord("f") and not self._result.problems and not self._flashed:
                self._flash()
            elif key == ord("r"):
                self._reset()
        elif self._capture_start is None:
            if key == ord(" ") and self._imu_ready():
                self._samples = []
                self._message = ""
                self._capture_start = dai.Clock.now() + SETTLE
            elif key == ord("b") and self._accel_means:
                self._accel_means.pop()
                self._gyro_means.pop()
                self._message = ""

    def _imu_ready(self) -> bool:
        # The IMU can take a few seconds to start streaming after pipeline start (seen on RVC4).
        return len(self._recent) == self._recent.maxlen

    def _finish_capture(self) -> None:
        self._capture_start = None
        samples = np.asarray(self._samples)
        if len(samples) < MIN_SAMPLES:
            self._message = (
                f"Only {len(samples)} IMU samples received. Press SPACE to retry."
            )
            return
        accel_mean = samples[:, :3].mean(axis=0)
        if not _is_still(samples[:, :3]):
            self._message = (
                "The device moved during the capture. Hold it still and press SPACE."
            )
            return
        if orientation_error(accel_mean, self._accel_means):
            self._message = (
                "Capture rejected: wrong orientation. Match the photo and press SPACE."
            )
            return
        self._accel_means.append(accel_mean)
        self._gyro_means.append(samples[:, 3:].mean(axis=0))
        if len(self._accel_means) == len(POSES):
            self._result = calibrate(
                np.asarray(self._accel_means), np.asarray(self._gyro_means)
            )
            self._save_report()

    def _save_report(self) -> None:
        self._output_dir.mkdir(parents=True, exist_ok=True)
        path = self._output_dir / f"imu_calibration_{datetime.now():%Y%m%d_%H%M%S}.json"
        report = {
            "mountingSource": self._mounting.source,
            "poseAccelerometerMeans": np.asarray(self._accel_means).tolist(),
            "poseGyroscopeMeans": np.asarray(self._gyro_means).tolist(),
            "rotation": self._result.rotation.tolist(),
            "accelerometer": self._result.accelerometer.tolist(),
            "gyroscope": self._result.gyroscope.tolist(),
            "poseErrors": self._result.pose_errors.tolist(),
            "problems": self._result.problems,
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
        print(self._message)

    def _render(self) -> np.ndarray:
        canvas = np.full((HEIGHT, WIDTH, 3), 22, dtype=np.uint8)
        cv2.rectangle(canvas, (0, 0), (WIDTH, 64), (10, 10, 14), -1)
        cv2.line(canvas, (0, 64), (WIDTH, 64), PINK, 2)
        if self._result is None:
            title, lines, wrap, footer = self._pose_view(canvas)
        else:
            title, lines, wrap, footer = self._result_view()
        cv2.putText(canvas, title, (24, 44), FONT, 1.0, WHITE, 2, cv2.LINE_AA)
        _draw_lines(canvas, lines, 24, 110, wrap)
        cv2.putText(canvas, footer, (24, HEIGHT - 24), FONT, 0.7, PINK, 2, cv2.LINE_AA)
        return canvas

    def _pose_view(self, canvas: np.ndarray) -> Tuple[str, List[Line], int, str]:
        idx = len(self._accel_means)
        x, y = PHOTO_ORIGIN
        photo = self._photos[idx]
        canvas[y : y + photo.shape[0], x : x + photo.shape[1]] = photo

        lines: List[Line] = [(POSES[idx].instruction, WHITE), ("", WHITE)]
        if self._capture_start is not None:
            elapsed = max(timedelta(0), dai.Clock.now() - self._capture_start)
            progress = min(1.0, elapsed / self._capture_duration)
            lines.append((f"Capturing... {progress:.0%}  Hold still.", GREEN))
            cv2.rectangle(canvas, (24, 600), (24 + int(500 * progress), 616), PINK, -1)
        elif not self._imu_ready():
            lines.append(("Waiting for IMU data...", GREY))
        else:
            recent = np.asarray(self._recent)
            still = _is_still(recent)
            lines.append(
                (
                    "Device is still." if still else "Device is moving.",
                    GREEN if still else RED,
                )
            )
            if self._accel_means:
                error = orientation_error(recent.mean(axis=0), self._accel_means)
                lines.append(
                    (error or "Orientation looks right.", RED if error else GREEN)
                )
        if self._message:
            lines += [("", WHITE), (self._message, RED)]
        return (
            f"IMU calibration - pose {idx + 1} of {len(POSES)}",
            lines,
            36,  # the photo takes the right side
            "SPACE capture    B previous pose    Q quit",
        )

    def _result_view(self) -> Tuple[str, List[Line], int, str]:
        result, mounting = self._result, self._mounting
        spec_note = ""
        if mounting.spec_rotation is not None:
            matches = np.allclose(result.rotation, mounting.spec_rotation)
            spec_note = (
                "  (matches depthai-boards)"
                if matches
                else "  (differs from depthai-boards spec)"
            )
        lines: List[Line] = [
            (
                f"Worst pose error after calibration: {result.pose_errors.max():.3f} m/s^2",
                WHITE,
            ),
            (f"IMU -> {mounting.socket.name} rotation{spec_note}:", GREY),
            *[(_fmt(row), WHITE) for row in result.rotation],
            ("Accelerometer [Q|b] (b in m/s^2):", GREY),
            *[(_fmt(row), WHITE) for row in result.accelerometer],
            (f"Gyroscope bias: {_fmt(result.gyroscope[:, 3])} rad/s", WHITE),
            (
                f"Translation: {_fmt(mounting.translation_cm)} cm from {mounting.source}",
                WHITE,
            ),
            ("", WHITE),
        ]
        problems = result.problems
        lines += [(p, RED) for p in problems] or [("All checks passed.", GREEN)]
        if self._message:
            lines.append((self._message, GREEN if self._flashed else RED))
        if self._flashed:
            footer = "R recalibrate    Q quit"
        elif problems:
            footer = "Flashing disabled.    R redo the capture    Q quit"
        else:
            footer = "F flash to device    R redo the capture    Q quit"
        return "IMU calibration - results", lines, 100, footer


def _is_still(accel: np.ndarray) -> bool:
    return np.linalg.norm(accel.std(axis=0)) <= MAX_ACCEL_STD


def _fmt(values) -> str:
    return "  ".join(f"{v:+.4f}" for v in values)


def _draw_lines(
    canvas: np.ndarray, lines: List[Line], x: int, y: int, width_chars: int
) -> None:
    for text, color in lines:
        for part in textwrap.wrap(text, width_chars) or [""]:
            cv2.putText(canvas, part, (x, y), FONT, 0.62, color, 1, cv2.LINE_AA)
            y += 28
