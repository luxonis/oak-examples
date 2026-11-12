import json
import logging
import os
import shutil
import zipfile
from pathlib import Path, PurePosixPath

from config import APP_IDENTIFIER, STORAGE_BASE_PATH
from services.application_logging import SNAPSHOT_PREFIX, LogExportWarning
from services.event_export.types import (
    ARCHIVE_PREFIX,
    ARCHIVE_SUFFIX,
    EventArchiveInfo,
    PreparedEventArchive,
)
from util.device_address import discover_device_ipv4_address

logger = logging.getLogger(__name__)


class EventArchiveStorage:
    """Archive filesystem operations; lifecycle synchronization belongs to the coordinator."""

    _EXPORT_DIRECTORY_NAME = "exports"
    _OAK_SHARED_STORAGE_HOST_ROOT = PurePosixPath(
        "/overlay/oak-agent/containers/app-storage/shared"
    )

    def __init__(self) -> None:
        self.directory = Path(STORAGE_BASE_PATH) / self._EXPORT_DIRECTORY_NAME
        self.directory.mkdir(parents=True, exist_ok=True)
        self._host_export_directory = (
            self._OAK_SHARED_STORAGE_HOST_ROOT
            / APP_IDENTIFIER
            / self._EXPORT_DIRECTORY_NAME
        )
        self._device_ipv4_address = discover_device_ipv4_address()

    def publish(
        self,
        prepared: PreparedEventArchive,
        previous_archive: EventArchiveInfo | None,
    ) -> EventArchiveInfo:
        partial_path = prepared.partial_path
        final_path = self.directory / prepared.filename
        with partial_path.open("rb") as partial_file:
            os.fsync(partial_file.fileno())
        if not zipfile.is_zipfile(partial_path):
            raise RuntimeError("The generated export archive is invalid")

        os.replace(partial_path, final_path)
        try:
            if previous_archive is not None and previous_archive.path != final_path:
                previous_archive.path.unlink(missing_ok=True)
        except Exception:
            final_path.unlink(missing_ok=True)
            raise
        self._fsync_directory()
        return self._describe_archive(
            final_path, prepared.event_count, prepared.created_at, prepared.warnings
        )

    def delete(self, archive: EventArchiveInfo) -> None:
        archive.path.unlink(missing_ok=True)
        self._fsync_directory()

    def reconcile(self) -> EventArchiveInfo | None:
        for snapshot_path in self.directory.glob(f"{SNAPSHOT_PREFIX}*"):
            # Never follow a symlink or remove anything outside our owned prefix.
            if snapshot_path.is_dir() and not snapshot_path.is_symlink():
                try:
                    shutil.rmtree(snapshot_path)
                except OSError:
                    logger.exception(
                        "Could not remove abandoned log snapshot %s", snapshot_path
                    )
        for partial_path in self.directory.glob(".*.zip.partial"):
            self._remove_leftover(partial_path)

        kept: EventArchiveInfo | None = None
        archives = sorted(self.directory.glob(f"{ARCHIVE_PREFIX}*{ARCHIVE_SUFFIX}"))
        for archive_path in reversed(archives):
            if kept is None:
                try:
                    kept = self._read_archive_info(archive_path)
                    continue
                except Exception:
                    logger.exception("Removing invalid export archive %s", archive_path)
            self._remove_leftover(archive_path)
        return kept

    @staticmethod
    def _remove_leftover(path: Path) -> None:
        # Startup cleanup is best effort: a leftover file must not stop the app
        try:
            path.unlink(missing_ok=True)
        except OSError:
            logger.exception("Could not remove leftover export file %s", path)

    def _read_archive_info(self, archive_path: Path) -> EventArchiveInfo:
        with zipfile.ZipFile(archive_path) as archive:
            manifest = json.loads(archive.read("manifest.json"))
        return self._describe_archive(
            archive_path,
            int(manifest["event_count"]),
            str(manifest["created_at"]),
            tuple(
                LogExportWarning(**warning) for warning in manifest.get("warnings", [])
            ),
        )

    def _describe_archive(
        self,
        archive_path: Path,
        event_count: int,
        created_at: str,
        warnings: tuple[LogExportWarning, ...],
    ) -> EventArchiveInfo:
        filename = archive_path.name
        return EventArchiveInfo(
            path=archive_path,
            filename=filename,
            host_path=str(self._host_export_directory / filename),
            byte_size=archive_path.stat().st_size,
            event_count=event_count,
            created_at=created_at,
            scp_command=self._make_scp_command(filename),
            warnings=warnings,
        )

    def _make_scp_command(self, filename: str) -> str:
        host = self._device_ipv4_address or "<oak-ip>"
        return f"scp root@{host}:{self._host_export_directory / filename} ."

    def _fsync_directory(self) -> None:
        descriptor = os.open(self.directory, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
