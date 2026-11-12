import logging
import shutil
import threading

from config import MIN_FREE_DISK_GB
from settings.settings_store import SettingsStore
from util.recording_files import RECORDINGS_DIR

logger = logging.getLogger(__name__)

_BYTES_PER_GB = 1024**3
_MIN_FREE_DISK_BYTES = int(MIN_FREE_DISK_GB * _BYTES_PER_GB)


class RecordingCleaner:
    """Deletes oldest continuous-recording chunks whenever their total size
    exceeds the configured cap. Never deletes the newest chunk, which may still
    be actively recording."""

    _cleanup_interval_seconds = 5.0

    def __init__(self, settings_store: SettingsStore):
        self._settings_store = settings_store
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="recording-storage-cleaner",
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
            self._cleanup()
            self._stop_event.wait(self._cleanup_interval_seconds)

    def _cleanup(self) -> None:
        max_bytes = int(
            self._settings_store.get().continuous_recording_max_storage_gb
            * _BYTES_PER_GB
        )
        try:
            self._prune_oldest_to_fit(max_bytes)
        except Exception:
            logger.exception(
                "Failed to enforce continuous recording storage limit of %s bytes",
                max_bytes,
            )

    def _prune_oldest_to_fit(self, max_bytes: int) -> None:
        if not RECORDINGS_DIR.is_dir():
            return

        # Filenames embed a UTC timestamp, so sorting by name is chronological.
        chunks = sorted(RECORDINGS_DIR.glob("recording-*.mp4"))
        if len(chunks) <= 1:
            return  # keep at least the (possibly in-progress) newest chunk

        sizes = {chunk: chunk.stat().st_size for chunk in chunks}
        total = sum(sizes.values())
        free = shutil.disk_usage(RECORDINGS_DIR).free

        removed = 0
        # Never touch the newest chunk, it may be recording.
        for chunk in chunks[:-1]:
            if total <= max_bytes and free >= _MIN_FREE_DISK_BYTES:
                break
            size = sizes[chunk]
            try:
                chunk.unlink(missing_ok=True)
            except OSError:
                logger.exception("Failed to remove recording chunk %s", chunk.name)
                continue
            total -= size
            free += size
            removed += 1

        if removed:
            logger.info(
                "Pruned %s old recording chunk(s) (cap=%s bytes, free floor=%s bytes)",
                removed,
                max_bytes,
                _MIN_FREE_DISK_BYTES,
            )
