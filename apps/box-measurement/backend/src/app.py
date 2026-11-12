import logging
import os
import shutil
import signal
import threading
from types import FrameType

import depthai as dai

from api.events import (
    DeleteEventRequest,
    DeleteEventResponse,
    delete_event,
    get_event_file,
    get_events,
)
from api.event_export import EventExportRequestHandler
from api.recordings import get_recording_file, get_recordings
from api.request_handler import (
    EmptyBody,
    add_binary_request_handler,
    add_request_handler,
)
from api.storage_info import get_storage_info
from config import STORAGE_BASE_PATH
from depthai_pipeline.init_pipeline import VISUALIZER_TOPICS, init_pipeline
from services.support_plane_controller import SupportPlaneController
from services.application_logging import ApplicationLoggingService
from services.event_cleaner import EventCleaner
from services.event_deletion_gate import EventDeletionGate
from services.event_export.coordinator import EventExportCoordinator
from services.recording_cleaner import RecordingCleaner
from settings.settings import (
    SetDetectionConfidenceThresholdRequest,
    SetSupportPlaneDistanceOffsetRequest,
    Settings,
)
from settings.settings_store import SettingsStore
from solutions_sdk.box_measurement import BoxMeasurer
from util.pipeline_latency_tracker import PipelineLatencyTracker

logger = logging.getLogger(__name__)


class App:
    def __init__(self, application_logging: ApplicationLoggingService):
        self.settings_store = SettingsStore()
        self.visualizer = dai.RemoteConnection(httpPort=8082)
        self.event_deletion_gate = EventDeletionGate()
        self.event_cleaner = EventCleaner(self.settings_store, self.event_deletion_gate)
        self.event_export_coordinator = EventExportCoordinator(
            self.settings_store, self.event_deletion_gate, application_logging
        )
        self.recording_cleaner = RecordingCleaner(self.settings_store)
        self._update_settings_event = threading.Event()
        self._shutdown_event = threading.Event()
        self._pipeline: dai.Pipeline | None = None
        self._support_plane: SupportPlaneController | None = None
        self._box_measurer: BoxMeasurer | None = None
        self._pipeline_latency_tracker: PipelineLatencyTracker | None = None

        add_request_handler(self.visualizer, "getSettings", self._get_settings)
        add_request_handler(self.visualizer, "updateSettings", self._update_settings)
        add_request_handler(
            self.visualizer,
            "setDetectionConfidenceThreshold",
            self._set_detection_confidence_threshold,
        )
        add_request_handler(self.visualizer, "getEvents", get_events)
        add_request_handler(self.visualizer, "deleteEvent", self._delete_event)
        add_binary_request_handler(self.visualizer, "getEventFile", get_event_file)
        add_request_handler(self.visualizer, "getRecordings", get_recordings)
        add_binary_request_handler(
            self.visualizer, "getRecordingFile", get_recording_file
        )
        add_request_handler(self.visualizer, "getStorageInfo", get_storage_info)
        EventExportRequestHandler(self.event_export_coordinator, self.visualizer)
        self._register_support_plane_services()

    def _handle_stop_signal(self, _signum: int, _frame: FrameType | None) -> None:
        logger.info("Received a stop signal, stopping the app")
        self._shutdown_event.set()

    def _get_settings(self, request: EmptyBody) -> Settings:
        return self.settings_store.get()

    def _update_settings(self, request: Settings) -> EmptyBody:
        self.settings_store.update(request)
        self._update_settings_event.set()
        return EmptyBody()

    def _delete_event(self, request: DeleteEventRequest) -> DeleteEventResponse:
        if not self.event_deletion_gate.try_begin_deletion():
            raise RuntimeError(
                "Events cannot be deleted while an export is in progress"
            )
        try:
            return delete_event(request)
        finally:
            self.event_deletion_gate.end_deletion()

    def _set_detection_confidence_threshold(
        self, request: SetDetectionConfidenceThresholdRequest
    ) -> EmptyBody:
        settings = self.settings_store.get().model_copy(
            update={"detection_confidence_threshold": request.threshold}
        )
        self.settings_store.update(settings)
        box_measurer = self._box_measurer
        if box_measurer is not None:
            try:
                box_measurer.setConfidenceThreshold(request.threshold)
            except dai.MessageQueue.QueueException:
                logger.warning(
                    "Pipeline is restarting; threshold applies on next start"
                )
        return EmptyBody()

    def _register_support_plane_services(self) -> None:
        self.visualizer.registerService(
            "getSupportPlaneCalibrationStatus",
            self._get_support_plane_calibration_status,
        )
        self.visualizer.registerService(
            "confirmSupportPlane",
            self._confirm_support_plane,
        )
        self.visualizer.registerService(
            "retrySupportPlaneCalibration",
            self._retry_support_plane_calibration,
        )
        self.visualizer.registerService(
            "selectSupportPlaneCandidate",
            self._select_support_plane_candidate,
        )
        self.visualizer.registerService(
            "setSupportPlanePreviewActive",
            self._set_support_plane_preview_active,
        )
        add_request_handler(
            self.visualizer,
            "setSupportPlaneDistanceOffset",
            self._set_support_plane_distance_offset,
        )

    def _get_support_plane_calibration_status(self, _request: dict) -> dict:
        controller = self._support_plane
        if controller is None:
            return {"error": "Support plane calibration is not available"}
        return controller.get_status()

    def _confirm_support_plane(self, _request: dict) -> dict:
        controller = self._support_plane
        if controller is None:
            return {"error": "Support plane calibration is not available"}
        if not controller.confirm_candidate():
            return {"error": "No support plane candidate is awaiting confirmation"}
        return {}

    def _retry_support_plane_calibration(self, _request: dict) -> dict:
        controller = self._support_plane
        if controller is None:
            return {"error": "Support plane calibration is not available"}
        controller.request_recalibration()
        return {}

    def _select_support_plane_candidate(self, request: dict) -> dict:
        controller = self._support_plane
        if controller is None:
            return {"error": "Support plane calibration is not available"}
        direction = int(request.get("direction", 1))
        if not controller.cycle_candidate(direction):
            return {"error": "No support plane candidate is awaiting confirmation"}
        return {}

    def _set_support_plane_preview_active(self, request: dict) -> dict:
        controller = self._support_plane
        if controller is None:
            return {"error": "Support plane calibration is not available"}
        controller.set_preview_active(bool(request.get("active", False)))
        return {}

    def _set_support_plane_distance_offset(
        self, request: SetSupportPlaneDistanceOffsetRequest
    ) -> EmptyBody:
        controller = self._support_plane
        if controller is None:
            raise RuntimeError("Support plane calibration is not available")
        controller.set_distance_offset(request.offset_mm)
        return EmptyBody()

    def _create_pipeline(self, settings: Settings) -> None:
        logger.info(
            f"Creating pipeline with settings: {settings.model_dump(mode='json')}"
        )
        pipeline = dai.Pipeline()
        pipeline.enablePipelineDebugging(True)
        (
            self._pipeline_latency_tracker,
            self._support_plane,
            self._box_measurer,
        ) = init_pipeline(
            pipeline=pipeline,
            settings=settings,
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

    def _remove_visualizer_topics(self) -> None:
        for topic in VISUALIZER_TOPICS.values():
            self.visualizer.removeTopic(topic)

    def _stop_pipeline(self) -> None:
        controller = self._support_plane
        self._support_plane = None
        if controller is not None:
            controller.close()
        if self._pipeline is None:
            return
        if self._pipeline.isRunning():
            logger.info("Stopping current pipeline")
            self._pipeline.stop()
            self._pipeline.wait()
        self._remove_visualizer_topics()
        self._pipeline = None
        self._support_plane = None
        self._box_measurer = None
        self._pipeline_latency_tracker = None

    def _restart_pipeline(self) -> None:
        self._stop_pipeline()
        self._create_pipeline(self.settings_store.get())

    def _log_storage_space(self) -> None:
        gb = 1024**3
        usage = shutil.disk_usage(STORAGE_BASE_PATH)
        stat = os.statvfs(STORAGE_BASE_PATH)
        available = stat.f_bavail * stat.f_frsize
        logger.info(
            "Storage at %s: total %.1f GB, free %.1f GB, available to app %.1f GB",
            STORAGE_BASE_PATH,
            usage.total / gb,
            usage.free / gb,
            available / gb,
        )

    def run(self):
        signal.signal(signal.SIGINT, self._handle_stop_signal)
        signal.signal(signal.SIGTERM, self._handle_stop_signal)

        self._log_storage_space()
        self.event_cleaner.start()
        self.recording_cleaner.start()
        try:
            self._restart_pipeline()

            while True:
                if self._shutdown_event.is_set():
                    break
                if self._pipeline is None or self._pipeline_latency_tracker is None:
                    raise RuntimeError("Pipeline runtime is not initialized")
                if not self._pipeline.isRunning():
                    logger.info("Pipeline is no longer running")
                    break

                self._pipeline.processTasks()
                self._pipeline_latency_tracker.check()

                if self._update_settings_event.is_set():
                    logger.info("Applying updated settings by recreating the pipeline")
                    self._update_settings_event.clear()
                    self._restart_pipeline()
                    continue

                key = self.visualizer.waitKey(1)
                if key == ord("q"):
                    logger.info("Got q key from the remote connection")
                    break
        finally:
            self._stop_pipeline()
            self.event_cleaner.stop()
            self.recording_cleaner.stop()
