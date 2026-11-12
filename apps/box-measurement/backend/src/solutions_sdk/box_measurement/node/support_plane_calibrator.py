"""Independent support-plane calibration on the node's own run loop."""

import time
from collections import deque
from enum import Enum

import depthai as dai
import numpy as np
from depthai_nodes.node import BaseThreadedHostNode

from solutions_sdk.box_measurement.helper.plane_validation import (
    gravity_angle_deg,
    is_valid_horizontal_plane,
)
from solutions_sdk.box_measurement.helper.support_plane_fitter import SupportPlaneFitter
from solutions_sdk.box_measurement.message.calibration import (
    CalibrationOutcome,
    PlaneCalibrationConfig,
    SupportPlaneCalibrationControl,
    SupportPlaneCalibrationResult,
    SupportPlaneVerificationResult,
)
from solutions_sdk.box_measurement.message.support_plane import SupportPlane

# Pause between run-loop passes, as DepthAI's DynamicCalibration does.
_PASS_SLEEP_SECONDS = 0.005


class _CalibratorState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETE = "complete"


class SupportPlaneCalibrator(BaseThreadedHostNode):
    """Search individual clouds until one qualifies, cancellation, or failure.

    Each run-loop pass applies pending controls, takes the latest IMU sample,
    answers verifications and, while running, fits the latest cloud. Controls
    wait during a fit, so Stop takes effect after the current fit: a fit that
    completes the attempt reports its outcome, otherwise the attempt ends
    cancelled. A cancelled attempt returns to idle; success or failure needs
    reset first. A start sent while an attempt is running is ignored.

    Verification is independent of attempts: each verify command produces one
    result on ``verification_out``, in order, once an IMU sample is available.

    A fit that raises ``ValueError`` or ``RuntimeError`` fails the attempt.
    Any other error is a bug and is not caught: DepthAI prints it with the
    raising line and aborts the process.

    Outputs use standard DepthAI buffering and backpressure.
    """

    def __init__(self) -> None:
        super().__init__()
        self.control_input: dai.Node.Input = self.createInput(name="control")
        self.out: dai.Node.Output = self.createOutput()
        self.verification_out: dai.Node.Output = self.createOutput(
            name="verification"
        )
        # Keep only the latest cloud, so idle never backpressures the shared
        # stream and a cloud arriving just before Start is still there for it.
        self._point_cloud: dai.Node.Input = self.createInput(
            name="point_cloud", blocking=False, queueSize=1
        )
        self._imu: dai.Node.Input = self.createInput(name="imu")
        self._state = _CalibratorState.IDLE
        self._built = False
        self._verifications: deque[SupportPlane] = deque()

    def build(
        self,
        point_cloud: dai.Node.Output,
        imu: dai.Node.Output,
        point_cloud_size: tuple[int, int],
        config: PlaneCalibrationConfig | None = None,
    ) -> "SupportPlaneCalibrator":
        if self._built:
            raise RuntimeError(
                "Calibration configuration is fixed; recreate the node to change it"
            )
        if len(point_cloud_size) != 2:
            raise ValueError("Point cloud size must be (width, height)")
        if any(
            isinstance(n, bool) or not isinstance(n, int) for n in point_cloud_size
        ):
            raise TypeError("Point cloud dimensions must be integers")
        if any(n <= 0 for n in point_cloud_size):
            raise ValueError("Point cloud dimensions must be positive")
        self._config = config if config is not None else PlaneCalibrationConfig()
        self._fitter = SupportPlaneFitter(point_cloud_size, self._config)
        point_cloud.link(self._point_cloud)
        imu.link(self._imu)
        self._built = True
        return self

    def run(self) -> None:
        latest_imu: dai.IMUData | None = None
        try:
            while self.isRunning():
                self._apply_controls()
                latest_imu = self._latest_imu(latest_imu)
                if latest_imu is not None:
                    self._answer_verifications(latest_imu)
                if self._state == _CalibratorState.RUNNING and latest_imu is not None:
                    cloud = self._point_cloud.tryGet()
                    if cloud is not None:
                        self._process_cloud(cloud, latest_imu)
                time.sleep(_PASS_SLEEP_SECONDS)
        # DepthAI's stub declares QueueException through an undeclared nested
        # class, so pyright cannot tell it is an exception; at runtime it is one.
        except dai.MessageQueue.QueueException:  # pyright: ignore[reportGeneralTypeIssues]
            return

    def _apply_controls(self) -> None:
        """Apply every pending control in arrival order.

        Controls that arrive during a fit wait here, so Stop takes effect
        after the current fit.
        """
        commands = SupportPlaneCalibrationControl.Commands
        while True:
            control = self.control_input.tryGet()
            if control is None:
                return
            if not isinstance(control, SupportPlaneCalibrationControl):
                continue
            command = control.command
            if isinstance(command, commands.Verify):
                self._verifications.append(command.plane)
            elif isinstance(command, commands.Start):
                if self._state == _CalibratorState.IDLE:
                    self._state = _CalibratorState.RUNNING
            elif isinstance(command, commands.Stop):
                if self._state == _CalibratorState.RUNNING:
                    self._finish(
                        CalibrationOutcome.CANCELLED, [], "Calibration cancelled"
                    )
            elif (
                isinstance(command, commands.Reset)
                and self._state != _CalibratorState.RUNNING
            ):
                self._state = _CalibratorState.IDLE

    def _latest_imu(self, latest: dai.IMUData | None) -> dai.IMUData | None:
        while True:
            imu = self._imu.tryGet()
            if imu is None:
                return latest
            if isinstance(imu, dai.IMUData):
                latest = imu

    def _finish(
        self, outcome: CalibrationOutcome, candidates: list[SupportPlane], info: str
    ) -> None:
        # Like DepthAI MultiDeviceCalibration, a stopped attempt needs no reset.
        self._state = (
            _CalibratorState.IDLE
            if outcome is CalibrationOutcome.CANCELLED
            else _CalibratorState.COMPLETE
        )
        self.out.send(SupportPlaneCalibrationResult(outcome, candidates, info))

    def _answer_verifications(self, imu: dai.IMUData) -> None:
        if not self._verifications:
            return
        gravity = _gravity(imu)
        if gravity is None:
            return
        max_angle = self._config.max_gravity_angle_deg
        while self._verifications:
            plane = self._verifications.popleft()
            plane_eq = np.array([*plane.normal, plane.offset_mm])
            self.verification_out.send(
                SupportPlaneVerificationResult(
                    plane,
                    gravity_angle_deg(plane_eq, gravity),
                    is_valid_horizontal_plane(plane_eq, gravity, max_angle),
                )
            )

    def _process_cloud(self, cloud: dai.ADatatype, imu: dai.IMUData) -> None:
        gravity = _gravity(imu)
        if gravity is None:
            return
        if not isinstance(cloud, dai.PointCloudData):
            self._finish(
                CalibrationOutcome.FAILED,
                [],
                "Calibration failed: expected organized PointCloudData",
            )
            return
        try:
            candidates = self._fitter.find_candidates(
                np.asarray(cloud.getPoints()), gravity
            )
        except (ValueError, RuntimeError) as exc:
            self._finish(CalibrationOutcome.FAILED, [], f"Calibration failed: {exc}")
            return
        if candidates:
            self._finish(
                CalibrationOutcome.SUCCEEDED, candidates, "Support planes found"
            )


def _gravity(imu: dai.IMUData) -> np.ndarray | None:
    """Raw accelerometer gravity from the first packet that carries it."""
    for packet in imu.packets:
        acceleration = packet.acceleroMeter
        if acceleration is not None:
            return np.array(
                [acceleration.x, acceleration.y, acceleration.z], dtype=np.float32
            )
    return None
