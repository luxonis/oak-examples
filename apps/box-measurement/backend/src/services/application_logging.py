"""Persistent application logging and rotation-safe copies for data exports."""

from __future__ import annotations

import errno
import logging
import logging.handlers
import shutil
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

LOG_MAX_BYTES = 2_000_000
LOG_BACKUP_COUNT = 9
SNAPSHOT_PREFIX = ".box-measurement-log-snapshot-"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


@dataclass(frozen=True)
class LogExportWarning:
    code: str
    message: str
    suggested_action: str
    file: str | None = None


def log_io_warning(error: Exception, file: str | None = None) -> LogExportWarning:
    error_number = getattr(error, "errno", None)
    if error_number in (errno.ENOSPC, errno.EDQUOT):
        return LogExportWarning(
            "logs_insufficient_space",
            "Logs could not be included because device storage has insufficient space.",
            "Free device storage and create a new archive.",
            file,
        )
    if error_number in (errno.EACCES, errno.EPERM):
        return LogExportWarning(
            "logs_permission_denied",
            "Logs could not be read because access was denied.",
            "Check device storage permissions.",
            file,
        )
    if error_number == errno.EROFS:
        return LogExportWarning(
            "logs_read_only",
            "Log storage is read-only.",
            "Check the device storage configuration.",
            file,
        )
    if error_number == errno.ENOENT:
        return LogExportWarning(
            "logs_missing_file",
            "A log file disappeared while preparing the export.",
            "Try creating a new archive.",
            file,
        )
    return LogExportWarning(
        "logs_io_error",
        f"Logs could not be included: {error}.",
        "Check device storage and try creating a new archive.",
        file,
    )


@dataclass(frozen=True)
class LogSnapshotFile:
    path: Path
    archive_path: str
    byte_size: int


@dataclass(frozen=True)
class LogSnapshot:
    directory: Path | None
    captured_at: str
    files: tuple[LogSnapshotFile, ...]
    warnings: tuple[LogExportWarning, ...]

    def cleanup(self) -> None:
        if self.directory is not None:
            try:
                shutil.rmtree(self.directory)
            except FileNotFoundError:
                pass
            except OSError:
                logging.getLogger(__name__).exception(
                    "Could not remove log snapshot %s", self.directory
                )


class _ResilientRotatingFileHandler(logging.handlers.RotatingFileHandler):
    _closed: bool
    _application_logging_service: ApplicationLoggingService | None = None

    def __init__(
        self,
        path: Path,
        max_bytes: int,
        backup_count: int,
        retry_interval_seconds: float,
    ):
        self.retry_interval_seconds = retry_interval_seconds
        self.failure_count = 0
        self.first_failure_at: str | None = None
        self.latest_failure_at: str | None = None
        self.latest_failure_reason: str | None = None
        self.recovered_at: str | None = None
        self._retry_at = 0.0
        self._diagnostic_at = float("-inf")
        super().__init__(
            path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
            delay=True,
        )
        self.setLevel(logging.INFO)
        formatter = logging.Formatter(
            "%(asctime)s.%(msecs)03dZ %(levelname)s %(name)s: %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
        formatter.converter = time.gmtime
        self.setFormatter(formatter)

    def _open(self):
        Path(self.baseFilename).parent.mkdir(parents=True, exist_ok=True)
        return super()._open()

    def _failed(self, error: Exception) -> None:
        now = _utc_now()
        self.failure_count += 1
        self.first_failure_at = self.first_failure_at or now
        self.latest_failure_at = now
        self.latest_failure_reason = str(error)
        self.recovered_at = None
        self._retry_at = time.monotonic() + self.retry_interval_seconds
        stream, self.stream = self.stream, None  # type: ignore[assignment]
        if stream is not None:
            try:
                stream.close()
            except Exception:  # noqa: BLE001, S110 - cannot log recursively from failure handling
                pass
        # Direct stderr output cannot recurse into this handler. Limit diagnostics
        # independently of the retry interval (including in tight retry tests).
        monotonic_now = time.monotonic()
        if monotonic_now - self._diagnostic_at >= 30:
            self._diagnostic_at = monotonic_now
            try:
                sys.stderr.write(
                    f"Application file logging failed; console logging continues: {error}\n"
                )
            except Exception:  # noqa: BLE001, S110 - cannot log recursively from failure handling
                pass

    def handleError(self, record: logging.LogRecord) -> None:
        error = sys.exc_info()[1]
        self._failed(
            error
            if isinstance(error, Exception)
            else RuntimeError("Unknown file logging failure")
        )

    def emit(self, record: logging.LogRecord) -> None:
        if self._closed or time.monotonic() < self._retry_at:
            return
        failure_count = self.failure_count
        try:
            super().emit(record)
        except Exception as error:  # noqa: BLE001 - file logging must never stop processing
            self._failed(error)
        if (
            self.failure_count == failure_count
            and self.latest_failure_at
            and not self.recovered_at
        ):
            self.recovered_at = _utc_now()

    def flush(self) -> None:
        self.acquire()
        try:
            try:
                super().flush()
            except Exception as error:  # noqa: BLE001 - file logging must never stop processing
                self._failed(error)
        finally:
            self.release()

    def close(self) -> None:
        self.acquire()
        try:
            try:
                super().close()
            except Exception as error:  # noqa: BLE001 - file logging must never stop processing
                self._failed(error)
                logging.Handler.close(self)
        finally:
            self.release()


class ApplicationLoggingService:
    def __init__(
        self,
        shared_storage_dir: Path,
        *,
        max_bytes: int = LOG_MAX_BYTES,
        backup_count: int = LOG_BACKUP_COUNT,
        retry_interval_seconds: float = 30.0,
    ):
        self.directory = Path(shared_storage_dir) / "logs"
        self.handler = _ResilientRotatingFileHandler(
            self.directory / "application.log",
            max_bytes,
            backup_count,
            retry_interval_seconds,
        )
        # Create an empty active file even before the first application message.
        try:
            self.handler.stream = self.handler._open()
        except Exception as error:  # noqa: BLE001 - file logging must never stop processing
            self.handler._failed(error)

    def health_warning(self) -> LogExportWarning | None:
        self.handler.acquire()
        try:
            if not self.handler.failure_count:
                return None
            recovery = (
                f" Writing recovered at {self.handler.recovered_at}."
                if self.handler.recovered_at
                else " File writing has not yet recovered."
            )
            return LogExportWarning(
                "log_history_incomplete",
                f"Log history may be incomplete: {self.handler.failure_count} file logging failure(s), first at {self.handler.first_failure_at}, latest at {self.handler.latest_failure_at}. Latest reason: {self.handler.latest_failure_reason}.{recovery}",
                "Check device storage and file logging; messages missed during the failure cannot be recovered.",
            )
        finally:
            self.handler.release()

    def snapshot(self, export_directory: Path) -> LogSnapshot:
        snapshot_directory: Path | None = None
        files: list[LogSnapshotFile] = []
        warnings: list[LogExportWarning] = []
        captured_at = _utc_now()
        self.handler.acquire()
        try:
            captured_at = _utc_now()
            try:
                self.handler.flush()
            except Exception as error:  # noqa: BLE001 - file logging must never stop processing
                self.handler._failed(error)
                warnings.append(log_io_warning(error, "logs/application.log"))
            health = self.health_warning()
            if health is not None:
                warnings.append(health)
            try:
                candidates = [
                    self.directory / f"application.log.{index}"
                    for index in range(self.handler.backupCount, 0, -1)
                ]
                candidates.append(self.directory / "application.log")
                sources: list[Path] = []
                size = 0
                for source in candidates:
                    try:
                        size += source.stat().st_size
                        sources.append(source)
                    except FileNotFoundError as error:
                        if source.name == "application.log":
                            warnings.append(
                                log_io_warning(error, "logs/application.log")
                            )
                    except OSError as error:
                        warnings.append(log_io_warning(error, f"logs/{source.name}"))
                if shutil.disk_usage(export_directory).free < size:
                    raise OSError(
                        errno.ENOSPC, "Not enough free space for temporary log copies"
                    )
                snapshot_directory = Path(
                    tempfile.mkdtemp(prefix=SNAPSHOT_PREFIX, dir=export_directory)
                )
                for source in sources:
                    destination = snapshot_directory / source.name
                    try:
                        shutil.copy2(source, destination)
                        files.append(
                            LogSnapshotFile(
                                destination,
                                f"logs/{source.name}",
                                destination.stat().st_size,
                            )
                        )
                    except OSError as error:
                        try:
                            destination.unlink(missing_ok=True)
                        except OSError as cleanup_error:
                            warnings.append(
                                log_io_warning(cleanup_error, f"logs/{source.name}")
                            )
                        if error.errno in (errno.ENOSPC, errno.EDQUOT):
                            raise
                        warnings.append(log_io_warning(error, f"logs/{source.name}"))
            except Exception as error:  # noqa: BLE001 - file logging must never stop processing
                warnings.append(log_io_warning(error))
                if snapshot_directory is not None:
                    # No logging or exporter locks while holding the handler lock.
                    try:
                        shutil.rmtree(snapshot_directory)
                        snapshot_directory = None
                    except OSError as cleanup_error:
                        warnings.append(log_io_warning(cleanup_error))
                files.clear()
        finally:
            self.handler.release()
        return LogSnapshot(
            snapshot_directory, captured_at, tuple(files), tuple(warnings)
        )

    def close(self) -> None:
        logging.getLogger().removeHandler(self.handler)
        self.handler.close()


_initialization_lock = threading.Lock()


def initialize_application_logging(
    shared_storage_dir: Path,
) -> ApplicationLoggingService:
    with _initialization_lock:
        root_logger = logging.getLogger()
        for handler in root_logger.handlers:
            service = getattr(handler, "_application_logging_service", None)
            if isinstance(service, ApplicationLoggingService):
                return service
        service = ApplicationLoggingService(shared_storage_dir)
        service.handler._application_logging_service = service
        root_logger.addHandler(service.handler)
        return service
