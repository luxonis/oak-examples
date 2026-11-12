from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TypeAlias

from services.application_logging import LogExportWarning

ARCHIVE_PREFIX = "box-export-"
ARCHIVE_SUFFIX = ".zip"

EventExportState: TypeAlias = Literal["absent", "preparing", "ready", "failed"]


@dataclass(frozen=True)
class EventArchiveInfo:
    path: Path
    filename: str
    host_path: str
    byte_size: int
    event_count: int
    created_at: str
    scp_command: str
    warnings: tuple[LogExportWarning, ...] = ()


@dataclass(frozen=True)
class EventExportStatus:
    state: EventExportState
    archive: EventArchiveInfo | None
    processed_event_count: int
    total_event_count: int
    failure_message: str | None


@dataclass(frozen=True)
class PreparedEventArchive:
    partial_path: Path
    filename: str
    event_count: int
    created_at: str
    warnings: tuple[LogExportWarning, ...]
