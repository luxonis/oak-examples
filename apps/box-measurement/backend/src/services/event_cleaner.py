import logging
import threading

from database.connection import DbSession
from database.repositories.event_repository import EventRepository
from services.event_deletion_gate import EventDeletionGate
from settings.settings_store import SettingsStore

logger = logging.getLogger(__name__)

_BYTES_PER_GB = 1024**3


class EventCleaner:
    """Deletes oldest events (rows + files) whenever their total file size
    exceeds the configured storage cap."""

    _cleanup_interval_seconds = 5.0

    def __init__(self, settings_store: SettingsStore, deletion_gate: EventDeletionGate):
        self._settings_store = settings_store
        self._deletion_gate = deletion_gate
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="event-retention-service",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        thread = self._thread
        self._thread = None

        if thread is not None and thread.is_alive():
            thread.join()

    def _run(self) -> None:
        while not self._stop_event.is_set():
            self._cleanup_old_events()
            self._stop_event.wait(self._cleanup_interval_seconds)

    def _cleanup_old_events(self) -> None:
        if not self._deletion_gate.try_begin_deletion():
            logger.debug("Skipping event retention while an export is in progress")
            return

        max_bytes = int(
            self._settings_store.get().event_storage_max_gb * _BYTES_PER_GB
        )
        try:
            with DbSession() as session:
                removed_count = EventRepository(session).prune_oldest_to_fit(max_bytes)
        except Exception:
            logger.exception(
                "Failed to enforce event storage limit of %s bytes", max_bytes
            )
            return
        finally:
            self._deletion_gate.end_deletion()

        if removed_count > 0:
            logger.info(
                "Pruned %s old event(s) to enforce the %s byte storage limit",
                removed_count,
                max_bytes,
            )
