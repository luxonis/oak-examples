import errno
import logging
import threading

from services.application_logging import ApplicationLoggingService
from services.event_deletion_gate import EventDeletionGate
from services.event_export.archive_builder import EventArchiveBuilder
from services.event_export.archive_storage import EventArchiveStorage
from services.event_export.types import (
    EventArchiveInfo,
    EventExportState,
    EventExportStatus,
)
from settings.settings_store import SettingsStore

logger = logging.getLogger(__name__)


class EventExportCoordinator:
    """Export state machine: builds one archive at a time in a background
    thread, for the user to copy off the device with scp."""

    def __init__(
        self,
        settings_store: SettingsStore,
        deletion_gate: EventDeletionGate,
        application_logging: ApplicationLoggingService,
    ) -> None:
        self._storage = EventArchiveStorage()
        self._builder = EventArchiveBuilder(
            settings_store, self._storage.directory, application_logging
        )
        self._deletion_gate = deletion_gate
        self._lock = threading.RLock()
        self._worker: threading.Thread | None = None
        self._archive: EventArchiveInfo | None = None
        self._state: EventExportState = "absent"
        self._processed_event_count = 0
        self._total_event_count = 0
        self._failure_message: str | None = None
        self._archive = self._storage.reconcile()
        if self._archive is not None:
            self._state = "ready"

    def get_status(self) -> EventExportStatus:
        with self._lock:
            return EventExportStatus(
                state=self._state,
                archive=self._archive,
                processed_event_count=self._processed_event_count,
                total_event_count=self._total_event_count,
                failure_message=self._failure_message,
            )

    def create_archive(self) -> EventExportStatus:
        with self._lock:
            if self._worker is not None:
                raise RuntimeError("An export operation is already in progress")

            self._deletion_gate.begin_export()
            self._state = "preparing"
            self._processed_event_count = 0
            self._total_event_count = 0
            self._failure_message = None
            worker = threading.Thread(
                target=self._create_archive_in_background,
                name="event-exporter",
                daemon=True,
            )
            self._worker = worker
            try:
                worker.start()
            except Exception:
                self._worker = None
                self._state = "ready" if self._archive is not None else "absent"
                self._deletion_gate.end_export()
                raise

            return self.get_status()

    def delete_archive(self) -> EventExportStatus:
        with self._lock:
            if self._worker is not None:
                raise RuntimeError("An export operation is already in progress")

            archive = self._archive
            if archive is not None:
                self._storage.delete(archive)

            self._archive = None
            self._state = "absent"
            self._processed_event_count = 0
            self._total_event_count = 0
            self._failure_message = None
            return self.get_status()

    def _create_archive_in_background(self) -> None:
        try:
            with self._lock:
                previous_archive = self._archive
            with self._builder.prepare(
                has_previous_archive=previous_archive is not None,
                report_progress=self._report_progress,
            ) as prepared:
                archive_info = self._storage.publish(prepared, previous_archive)
                with self._lock:
                    self._archive = archive_info
                    self._failure_message = None
        except Exception as error:
            logger.exception("Event export failed")
            with self._lock:
                self._state = "failed"
                self._failure_message = (
                    "Not enough free space on device storage to write the export archive. Free storage and try again."
                    if isinstance(error, OSError)
                    and error.errno in (errno.ENOSPC, errno.EDQUOT)
                    else str(error)
                )
        finally:
            self._deletion_gate.end_export()
            with self._lock:
                self._worker = None
                if self._state == "preparing":
                    self._state = "ready"

    def _report_progress(self, processed: int, total: int) -> None:
        with self._lock:
            self._processed_event_count = processed
            self._total_event_count = total
