"""Run SafeGuard with live controls and a process-local event history."""

import logging
import threading

import depthai as dai

from api.events import (
    GetEventFileRequest,
    GetEventsRequest,
    GetEventsResponse,
    get_events,
)
from api.request_handler import (
    EmptyBody,
    add_binary_request_handler,
    add_request_handler,
)
from depthai_pipeline.init_pipeline import init_pipeline
from events.event_store import EventStore
from settings.settings import Settings

log = logging.getLogger(__name__)


class App:
    """Own the live pipeline, remote services, and process-local event store."""

    def __init__(self) -> None:
        self._settings = Settings.from_env()
        self._settings_lock = threading.Lock()
        self._changed = threading.Event()
        self._store = EventStore(self._settings.event_retention_count)
        self._visualizer = dai.RemoteConnection(httpPort=8082)
        self._pipeline: dai.Pipeline | None = None
        self._topics: tuple[str, ...] = ()
        add_request_handler(self._visualizer, "getSettings", self._get_settings)
        add_request_handler(self._visualizer, "updateSettings", self._update_settings)
        add_request_handler(self._visualizer, "getEvents", self._get_events)
        add_binary_request_handler(
            self._visualizer, "getEventFile", self._get_event_file
        )

    def _get_settings(self, request: EmptyBody) -> Settings:
        with self._settings_lock:
            return self._settings.model_copy(deep=True)

    def _update_settings(self, request: Settings) -> EmptyBody:
        """Apply retention now and restart the pipeline with new runtime settings."""
        with self._settings_lock:
            self._settings = request.model_copy(deep=True)
            self._store.set_limit(request.event_retention_count)
            self._changed.set()
        return EmptyBody()

    def _get_events(self, request: GetEventsRequest) -> GetEventsResponse:
        return get_events(self._store, request)

    def _get_event_file(self, request: GetEventFileRequest) -> bytes | None:
        return self._store.read_file(request.path)

    def _stop_pipeline(self) -> None:
        """Stop processing and unregister topics from the previous pipeline."""
        if self._pipeline is not None and self._pipeline.isRunning():
            self._pipeline.stop()
            self._pipeline.wait()
        for topic in self._topics:
            self._visualizer.removeTopic(topic)
        self._pipeline = None
        self._topics = ()

    def _start_pipeline(self) -> None:
        settings = self._get_settings(EmptyBody())
        log.info("SafeGuard settings: %s", settings.model_dump(mode="json"))
        pipeline = dai.Pipeline()
        topics = init_pipeline(pipeline, settings, self._visualizer, self._store)
        pipeline.start()
        self._visualizer.registerPipeline(pipeline)
        self._pipeline = pipeline
        self._topics = topics
        log.info("Pipeline started.")

    def run(self) -> None:
        """Process pipeline tasks until exit, then remove temporary event files."""
        try:
            self._start_pipeline()
            while self._pipeline is not None and self._pipeline.isRunning():
                self._pipeline.processTasks()
                if self._changed.is_set():
                    self._changed.clear()
                    self._stop_pipeline()
                    self._start_pipeline()
                    continue
                if self._visualizer.waitKey(1) == ord("q"):
                    break
        finally:
            self._stop_pipeline()
            self._store.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    App().run()
