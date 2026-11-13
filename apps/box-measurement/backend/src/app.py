import logging
import signal
import threading
from types import FrameType
from typing import Literal

import depthai as dai
from depthai_nodes.node import BoxMeasurer
from pydantic import BaseModel, Field

from api.request_handler import EmptyBody, add_request_handler
from config import DEFAULT_DETECTION_CONFIDENCE_THRESHOLD
from depthai_pipeline.init_pipeline import init_pipeline
from services.support_plane_controller import SupportPlaneController

logger = logging.getLogger(__name__)


class DetectionConfidenceThreshold(BaseModel):
    threshold: float = Field(ge=0.0, le=1.0)


class SetSupportPlaneDistanceOffsetRequest(BaseModel):
    offset_mm: float = Field(ge=-100.0, le=100.0)


class SupportPlaneCalibrationStatus(BaseModel):
    state: Literal["SEARCHING", "AWAITING_CONFIRMATION", "CONFIRMED"]
    candidate_count: int
    selected_index: int
    distance_offset_mm: float
    camera_tilt_deg: float | None
    camera_distance_mm: float | None


class SelectSupportPlaneCandidateRequest(BaseModel):
    direction: Literal[1, -1]


class SetSupportPlanePreviewActiveRequest(BaseModel):
    active: bool


class App:
    def __init__(self) -> None:
        self.visualizer = dai.RemoteConnection(httpPort=8082)
        self._detection_confidence_threshold = DEFAULT_DETECTION_CONFIDENCE_THRESHOLD
        self._shutdown_event = threading.Event()
        self._pipeline: dai.Pipeline | None = None
        self._support_plane: SupportPlaneController | None = None
        self._box_measurer: BoxMeasurer | None = None

        add_request_handler(
            self.visualizer,
            "getDetectionConfidenceThreshold",
            self._get_detection_confidence_threshold,
        )
        add_request_handler(
            self.visualizer,
            "setDetectionConfidenceThreshold",
            self._set_detection_confidence_threshold,
        )
        self._register_support_plane_services()

    def _handle_stop_signal(self, _signum: int, _frame: FrameType | None) -> None:
        logger.info("Received a stop signal, stopping the app")
        self._shutdown_event.set()

    def _get_detection_confidence_threshold(
        self, request: EmptyBody
    ) -> DetectionConfidenceThreshold:
        return DetectionConfidenceThreshold(
            threshold=self._detection_confidence_threshold
        )

    def _set_detection_confidence_threshold(
        self, request: DetectionConfidenceThreshold
    ) -> EmptyBody:
        self._detection_confidence_threshold = request.threshold
        if self._box_measurer is not None:
            self._box_measurer.setConfidenceThreshold(request.threshold)
        return EmptyBody()

    def _register_support_plane_services(self) -> None:
        for service_name, handler in (
            (
                "getSupportPlaneCalibrationStatus",
                self._get_support_plane_calibration_status,
            ),
            ("confirmSupportPlane", self._confirm_support_plane),
            ("retrySupportPlaneCalibration", self._retry_support_plane_calibration),
            ("selectSupportPlaneCandidate", self._select_support_plane_candidate),
            ("setSupportPlanePreviewActive", self._set_support_plane_preview_active),
            ("setSupportPlaneDistanceOffset", self._set_support_plane_distance_offset),
        ):
            add_request_handler(self.visualizer, service_name, handler)

    def _controller(self) -> SupportPlaneController:
        controller = self._support_plane
        if controller is None:
            raise RuntimeError("Support plane calibration is not available")
        return controller

    def _get_support_plane_calibration_status(
        self, request: EmptyBody
    ) -> SupportPlaneCalibrationStatus:
        return SupportPlaneCalibrationStatus.model_validate(
            self._controller().get_status()
        )

    def _confirm_support_plane(self, request: EmptyBody) -> EmptyBody:
        if not self._controller().confirm_candidate():
            raise RuntimeError("No support plane candidate is awaiting confirmation")
        return EmptyBody()

    def _retry_support_plane_calibration(self, request: EmptyBody) -> EmptyBody:
        self._controller().request_recalibration()
        return EmptyBody()

    def _select_support_plane_candidate(
        self, request: SelectSupportPlaneCandidateRequest
    ) -> EmptyBody:
        if not self._controller().cycle_candidate(request.direction):
            raise RuntimeError("No support plane candidate is awaiting confirmation")
        return EmptyBody()

    def _set_support_plane_preview_active(
        self, request: SetSupportPlanePreviewActiveRequest
    ) -> EmptyBody:
        self._controller().set_preview_active(request.active)
        return EmptyBody()

    def _set_support_plane_distance_offset(
        self, request: SetSupportPlaneDistanceOffsetRequest
    ) -> EmptyBody:
        self._controller().set_distance_offset(request.offset_mm)
        return EmptyBody()

    def _create_pipeline(self) -> dai.Pipeline:
        pipeline = dai.Pipeline()
        self._support_plane, self._box_measurer = init_pipeline(
            pipeline=pipeline,
            confidence_threshold=self._detection_confidence_threshold,
            visualizer=self.visualizer,
        )
        self._pipeline = pipeline
        try:
            pipeline.start()
            logger.info("Pipeline started.")
            self._support_plane.start()
            self.visualizer.registerPipeline(pipeline)
        except Exception:
            self._stop_pipeline()
            raise
        return pipeline

    def _stop_pipeline(self) -> None:
        controller = self._support_plane
        self._support_plane = None
        if controller is not None:
            controller.close()
        if self._pipeline is not None and self._pipeline.isRunning():
            logger.info("Stopping the pipeline")
            self._pipeline.stop()
            self._pipeline.wait()

    def run(self):
        signal.signal(signal.SIGINT, self._handle_stop_signal)
        signal.signal(signal.SIGTERM, self._handle_stop_signal)

        try:
            pipeline = self._create_pipeline()

            while True:
                if self._shutdown_event.is_set():
                    break
                if not pipeline.isRunning():
                    logger.info("Pipeline is no longer running")
                    break

                pipeline.processTasks()

                key = self.visualizer.waitKey(1)
                if key == ord("q"):
                    logger.info("Got q key from the remote connection")
                    break
        finally:
            self._stop_pipeline()
