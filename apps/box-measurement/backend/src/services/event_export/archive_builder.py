import errno
import json
import shutil
import zipfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from config import (
    APP_IDENTIFIER,
    APP_VERSION,
    BOX_MODEL_SLUG,
    COLOR_RESOLUTION,
    MONO_RESOLUTION,
    NEURAL_DEPTH_MODEL,
)
from database.connection import DbSession
from database.models.event import MeasurementEvent
from database.repositories.event_repository import EventRepository
from services.application_logging import (
    ApplicationLoggingService,
    LogSnapshot,
    log_io_warning,
)
from services.event_export.types import (
    ARCHIVE_PREFIX,
    ARCHIVE_SUFFIX,
    PreparedEventArchive,
)
from settings.settings_store import SettingsStore
from util.event_files import resolve_event_file_path


@dataclass(frozen=True)
class _EventFileEntry:
    event_id: int
    name: str
    relative_path: str
    archive_path: str


class EventArchiveBuilder:
    """Builds one partial ZIP of all events, settings, support plane and logs,
    and keeps its temporary resources until it is published."""

    _MINIMUM_SPACE_MARGIN_BYTES = 10 * 1024 * 1024

    def __init__(
        self,
        settings_store: SettingsStore,
        export_directory: Path,
        application_logging: ApplicationLoggingService,
    ) -> None:
        self._settings_store = settings_store
        self._export_directory = export_directory
        self._application_logging = application_logging

    @contextmanager
    def prepare(
        self,
        has_previous_archive: bool,
        report_progress: Callable[[int, int], None],
    ) -> Iterator[PreparedEventArchive]:
        snapshot = None
        try:
            try:
                snapshot = self._application_logging.snapshot(self._export_directory)
            except Exception as error:  # noqa: BLE001 - logs are optional
                snapshot = LogSnapshot(
                    None,
                    datetime.now(timezone.utc).isoformat(),
                    (),
                    (log_io_warning(error),),
                )
            with self._write_partial(
                snapshot, has_previous_archive, report_progress
            ) as prepared:
                yield prepared
        finally:
            if snapshot is not None:
                snapshot.cleanup()

    @contextmanager
    def _write_partial(
        self,
        snapshot: LogSnapshot,
        has_previous_archive: bool,
        report_progress: Callable[[int, int], None],
    ) -> Iterator[PreparedEventArchive]:
        created_at = datetime.now(timezone.utc)
        created_at_text = created_at.isoformat(timespec="seconds").replace(
            "+00:00", "Z"
        )
        filename = (
            f"{ARCHIVE_PREFIX}{created_at.strftime('%Y%m%dT%H%M%SZ')}{ARCHIVE_SUFFIX}"
        )
        partial_path = self._export_directory / f".{filename}.partial"

        event_lines: list[str] = []
        file_entries: list[_EventFileEntry] = []
        with DbSession() as session:
            events = EventRepository(session).get_all_oldest_first()
            for event in events:
                event_data, event_files = self._serialize_event(event)
                event_lines.append(json.dumps(event_data, separators=(",", ":")))
                file_entries.extend(event_files)
        event_ids = [event.id for event in events]
        settings = self._settings_store.get().model_dump(mode="json")

        report_progress(0, len(event_ids))

        files_by_event: dict[int, list[tuple[Path, str]]] = {}
        missing_files: list[dict[str, object]] = []
        file_bytes = 0
        for entry in file_entries:
            try:
                source_path = resolve_event_file_path(entry.relative_path)
                file_bytes += source_path.stat().st_size
            except OSError:
                missing_files.append(
                    {
                        "event_id": entry.event_id,
                        "file_name": entry.name,
                        "archive_path": entry.archive_path,
                    }
                )
                continue
            files_by_event.setdefault(entry.event_id, []).append(
                (source_path, entry.archive_path)
            )

        events_jsonl = "\n".join(event_lines)
        if event_lines:
            events_jsonl += "\n"
        settings_json = json.dumps(settings, indent=2, sort_keys=True) + "\n"
        log_files = list(snapshot.files)
        warnings = list(snapshot.warnings)
        manifest: dict[str, Any] = {
            "schema_version": 1,
            "created_at": created_at_text,
            "application": {
                "identifier": APP_IDENTIFIER,
                "version": APP_VERSION,
            },
            "pipeline": {
                "box_model": BOX_MODEL_SLUG,
                "depth_model": NEURAL_DEPTH_MODEL,
                "color_resolution": list(COLOR_RESOLUTION),
                "mono_resolution": list(MONO_RESOLUTION),
            },
            "event_count": len(event_ids),
            "events_file": "events/events.jsonl",
            "configuration_files": {
                "settings": "configuration/settings.json",
            },
            "missing_files": missing_files,
            "log_snapshot": {
                "captured_at": snapshot.captured_at,
                "files": [],
                "reading_order": [],
            },
            "warnings": [asdict(warning) for warning in warnings],
        }
        manifest_json = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
        estimated_bytes = (
            file_bytes
            + sum(file.byte_size for file in log_files)
            + len(events_jsonl.encode("utf-8"))
            + len(settings_json.encode("utf-8"))
            + len(manifest_json.encode("utf-8"))
        )
        free_bytes = shutil.disk_usage(self._export_directory).free
        required_bytes = self._with_space_margin(estimated_bytes)
        if free_bytes < required_bytes and log_files:
            # The event data takes priority over optional log history.
            estimated_bytes -= sum(file.byte_size for file in log_files)
            log_files.clear()
            warnings.append(
                log_io_warning(
                    OSError(
                        errno.ENOSPC, "Not enough space to include logs in the archive"
                    )
                )
            )
            snapshot.cleanup()
            free_bytes = shutil.disk_usage(self._export_directory).free
            required_bytes = self._with_space_margin(estimated_bytes)
        if free_bytes < required_bytes:
            delete_advice = (
                " Delete the existing archive and try again."
                if has_previous_archive
                else ""
            )
            raise RuntimeError(
                "Not enough free space to create the archive: "
                f"{required_bytes} bytes required, {free_bytes} bytes available."
                f"{delete_advice}"
            )

        partial_path.unlink(missing_ok=True)
        try:
            with zipfile.ZipFile(
                partial_path,
                mode="w",
                compression=zipfile.ZIP_DEFLATED,
                allowZip64=True,
            ) as archive:
                archive.writestr("configuration/settings.json", settings_json)
                archive.writestr("events/events.jsonl", events_jsonl)

                # JPEG and MP4 are already compressed: store them as they are
                for index, event_id in enumerate(event_ids, start=1):
                    for source_path, archive_path in files_by_event.get(event_id, []):
                        archive.write(
                            source_path,
                            archive_path,
                            compress_type=zipfile.ZIP_STORED,
                        )
                    report_progress(index, len(event_ids))

                included_logs = []
                for log_file in log_files:
                    try:
                        # Read a whole staged file before opening its ZIP member:
                        # read errors cannot leave a damaged member in the ZIP.
                        content = log_file.path.read_bytes()
                    except OSError as error:
                        warnings.append(log_io_warning(error, log_file.archive_path))
                        continue
                    archive.writestr(log_file.archive_path, content)
                    included_logs.append(
                        {"path": log_file.archive_path, "byte_size": len(content)}
                    )
                manifest["log_snapshot"]["files"] = included_logs
                manifest["log_snapshot"]["reading_order"] = [
                    entry["path"] for entry in included_logs
                ]
                manifest["warnings"] = [asdict(warning) for warning in warnings]
                archive.writestr(
                    "manifest.json",
                    json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                )

            yield PreparedEventArchive(
                partial_path=partial_path,
                filename=filename,
                event_count=len(event_ids),
                created_at=created_at_text,
                warnings=tuple(warnings),
            )
        except Exception:
            partial_path.unlink(missing_ok=True)
            raise

    @staticmethod
    def _serialize_event(
        event: MeasurementEvent,
    ) -> tuple[dict[str, object], list[_EventFileEntry]]:
        event_directory = PurePosixPath("events", "files", str(event.id))
        entries = [
            _EventFileEntry(
                event_id=event.id,
                name=saved_file.name,
                relative_path=saved_file.path,
                archive_path=str(
                    event_directory
                    / f"{saved_file.name}{PurePosixPath(saved_file.path).suffix}"
                ),
            )
            for saved_file in event.files
        ]
        # SQLite drops the timezone; stored values are UTC
        created_at = event.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        event_data: dict[str, object] = {
            "event_id": event.id,
            "event_type": event.event_type.value,
            "track_id": event.track_id,
            "created_at": created_at.astimezone(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
            "length_mm": event.length_mm,
            "width_mm": event.width_mm,
            "height_mm": event.height_mm,
            "volume_mm3": event.volume_mm3,
            "files": {entry.name: entry.archive_path for entry in entries},
        }
        return event_data, entries

    def _with_space_margin(self, estimated_bytes: int) -> int:
        return estimated_bytes + max(
            self._MINIMUM_SPACE_MARGIN_BYTES, estimated_bytes // 50
        )
