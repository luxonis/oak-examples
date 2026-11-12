"""Application calibration workflow, independent of the SDK fitting lifecycle."""

import logging
from threading import Event, RLock, Thread

import depthai as dai
import numpy as np

from solutions_sdk.box_measurement import (
    BoxMeasurer,
    CalibrationOutcome,
    SupportPlane,
    SupportPlaneCalibrationControl,
    SupportPlaneCalibrationResult,
    SupportPlaneCalibrator,
    SupportPlaneVerificationResult,
)
from util.plane_geometry import (
    apply_distance_offset,
    camera_distance_mm,
    camera_tilt_deg,
)
from util.support_plane_store import clear_plane, load_plane, save_plane

logger = logging.getLogger(__name__)


def plane_equation(plane: SupportPlane) -> np.ndarray:
    return np.array([*plane.normal, plane.offset_mm], dtype=np.float64)


class SupportPlaneController:
    """Own selection, activation and storage; consume each attempt before retrying."""

    def __init__(self, calibrator: SupportPlaneCalibrator, measurer: BoxMeasurer):
        self._controls = calibrator.control_input.createInputQueue()
        self._results = calibrator.out.createOutputQueue()
        self._verifications = calibrator.verification_out.createOutputQueue()
        self._measurer = measurer
        self._lock = RLock()
        self._closed = Event()
        self._consumer: Thread | None = None
        self._outstanding = False
        self._completed = False
        self._restart_pending = False
        self._error: str | None = None
        self._state = "SEARCHING"
        self._candidates: list[SupportPlane] = []
        self._selected = 0
        self._active: SupportPlane | None = None
        self._corrected: SupportPlane | None = None
        self._preview_active = False
        self._offset_mm = 0.0
        saved = load_plane()
        self._restored: SupportPlane | None = None
        if saved is not None:
            self._restored, self._offset_mm = saved
            self._state = "RESTORING"

    def start(self) -> None:
        with self._lock:
            if self._consumer is not None or self._closed.is_set():
                return
            self._consumer = Thread(
                target=self._consume_results, name="plane-results", daemon=True
            )
            if self._state == "SEARCHING":
                self._start_attempt()
            elif self._restored is not None:
                # The calibrator owns the gravity check; restoration owns the policy.
                self._controls.send(
                    SupportPlaneCalibrationControl.verify(self._restored)
                )
            self._consumer.start()

    def _start_attempt(self) -> None:
        if self._closed.is_set() or self._outstanding or self._consumer is None:
            return
        if self._completed:
            self._controls.send(SupportPlaneCalibrationControl.reset())
        self._outstanding = True
        self._restart_pending = False
        self._controls.send(SupportPlaneCalibrationControl.start())

    def _consume_results(self) -> None:
        try:
            while not self._closed.is_set():
                verification = self._verifications.tryGet()
                if isinstance(verification, SupportPlaneVerificationResult):
                    self._restore(verification)
                result = self._results.tryGet()
                if result is None:
                    self._closed.wait(0.005)
                    continue
                if not isinstance(result, SupportPlaneCalibrationResult):
                    continue
                with self._lock:
                    if self._closed.is_set() or not self._outstanding:
                        continue
                    self._outstanding = False
                    self._completed = True
                    if self._restart_pending:
                        self._start_attempt()
                    elif result.outcome is CalibrationOutcome.SUCCEEDED:
                        self._candidates = list(result.candidates)
                        self._selected = 0
                        self._state = "AWAITING_CONFIRMATION"
                    elif result.outcome is CalibrationOutcome.FAILED:
                        self._error = result.info
        except dai.MessageQueue.QueueException:
            return

    def close(self) -> None:
        """Detach before pipeline replacement, without waiting for an executing fit."""
        with self._lock:
            if self._closed.is_set():
                return
            self._closed.set()
            if self._outstanding:
                try:
                    self._controls.send(SupportPlaneCalibrationControl.stop())
                except dai.MessageQueue.QueueException:
                    pass
        if self._consumer is not None:
            self._consumer.join(timeout=1)
        for queue in (self._results, self._verifications):
            try:
                while queue.tryGet() is not None:
                    pass
            except dai.MessageQueue.QueueException:
                pass

    def request_recalibration(self) -> None:
        with self._lock:
            if self._closed.is_set():
                return
            self._state = "SEARCHING"
            self._candidates = []
            self._selected = 0
            self._error = None
            self._restored = self._active = self._corrected = None
            self._offset_mm = 0.0
            self._measurer.clearSupportPlane()
            if self._outstanding:
                if not self._restart_pending:
                    self._restart_pending = True
                    self._controls.send(SupportPlaneCalibrationControl.stop())
            else:
                self._start_attempt()
            clear_plane()

    def _restore(self, verification: SupportPlaneVerificationResult) -> None:
        """Activate the saved plane if the calibrator accepted it, else search."""
        with self._lock:
            # A restart or replacement abandons the saved plane being verified.
            if (
                self._closed.is_set()
                or self._state != "RESTORING"
                or verification.plane != self._restored
            ):
                return
            plane = verification.plane
            self._restored = None
            if verification.accepted:
                try:
                    corrected_eq = apply_distance_offset(
                        plane_equation(plane), self._offset_mm
                    )
                except ValueError:
                    self._offset_mm = 0.0
                    corrected_eq = plane_equation(plane)
                self._active = plane
                self._corrected = SupportPlane(
                    normal=tuple(corrected_eq[:3]), offset_mm=float(corrected_eq[3])
                )
                self._measurer.setSupportPlane(self._corrected)
                self._state = "CONFIRMED"
            else:
                self._offset_mm = 0.0
                self._state = "SEARCHING"
                try:
                    clear_plane()
                except OSError:
                    logger.exception("Rejected saved calibration could not be removed")
                self._start_attempt()

    def confirm_candidate(self) -> bool:
        with self._lock:
            plane = self._selected_candidate()
            if plane is None:
                return False
            self._active = self._corrected = plane
            self._offset_mm = 0.0
            self._state = "CONFIRMED"
            self._measurer.setSupportPlane(plane)
            # Persistence is separate from activation; errors must reach the service.
            save_plane(plane)
            return True

    def cycle_candidate(self, direction: int = 1) -> bool:
        with self._lock:
            if self._selected_candidate() is None:
                return False
            self._selected = (self._selected + direction) % len(self._candidates)
            return True

    def _selected_candidate(self) -> SupportPlane | None:
        if (
            self._closed.is_set()
            or self._state != "AWAITING_CONFIRMATION"
            or not self._candidates
            or self._error
        ):
            return None
        return self._candidates[self._selected]

    def _displayed_plane(self) -> SupportPlane | None:
        if self._active is not None:
            return self._active
        return self._candidates[self._selected] if self._candidates else None

    def set_distance_offset(self, offset_mm: float) -> None:
        with self._lock:
            if (
                self._closed.is_set()
                or self._state != "CONFIRMED"
                or self._active is None
            ):
                raise RuntimeError(
                    "The support plane must be confirmed before setting an offset"
                )
            if offset_mm == self._offset_mm:
                return
            equation = apply_distance_offset(plane_equation(self._active), offset_mm)
            self._corrected = SupportPlane(
                normal=tuple(equation[:3]), offset_mm=float(equation[3])
            )
            self._offset_mm = offset_mm
            self._measurer.setSupportPlane(self._corrected)
            save_plane(self._active, offset_mm)

    def set_preview_active(self, active: bool) -> None:
        with self._lock:
            if not self._closed.is_set():
                self._preview_active = active

    def preview_data(
        self,
    ) -> tuple[bool, SupportPlane | None, SupportPlane | None, bool]:
        with self._lock:
            plane = self._displayed_plane()
            return (
                self._preview_active and not self._closed.is_set(),
                plane,
                self._corrected or plane,
                self._active is not None,
            )

    def get_status(self) -> dict[str, str | int | float | None]:
        with self._lock:
            if self._closed.is_set():
                return {"error": "Support plane calibration is not available"}
            if self._error is not None:
                return {"error": self._error}
            plane = self._displayed_plane()
            corrected = self._corrected or plane
            status: dict[str, str | int | float | None] = {
                "state": self._state,
                "candidate_count": len(self._candidates),
                "selected_index": self._selected,
                "distance_offset_mm": self._offset_mm,
                "camera_tilt_deg": None,
                "camera_distance_mm": None,
                "corrected_camera_distance_mm": None,
            }
            if plane is not None and corrected is not None:
                status["camera_tilt_deg"] = round(
                    camera_tilt_deg(plane_equation(plane)), 1
                )
                distance = camera_distance_mm(plane_equation(plane))
                corrected_distance = camera_distance_mm(plane_equation(corrected))
                if distance is not None and corrected_distance is not None:
                    status["camera_distance_mm"] = round(distance, 1)
                    status["corrected_camera_distance_mm"] = round(
                        corrected_distance, 1
                    )
            return status
