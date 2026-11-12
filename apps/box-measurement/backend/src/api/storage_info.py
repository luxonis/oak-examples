import logging
import os
import shutil
from pathlib import Path

from pydantic import BaseModel

from config import MIN_FREE_DISK_GB, STORAGE_BASE_PATH
from util.event_files import EVENT_FILES_DIR
from util.recording_files import RECORDINGS_DIR

logger = logging.getLogger(__name__)

_BYTES_PER_GB = 1024**3


class EmptyRequest(BaseModel):
    pass


class StorageInfoResponse(BaseModel):
    total_bytes: int
    free_bytes: int
    available_bytes: int
    recordings_bytes: int
    events_bytes: int
    min_free_floor_bytes: int


def _dir_size(path: Path) -> int:
    if not path.is_dir():
        return 0
    total = 0
    for entry in path.rglob("*"):
        try:
            if entry.is_file():
                total += entry.stat().st_size
        except OSError:
            continue
    return total


def get_storage_info(request: EmptyRequest) -> StorageInfoResponse:
    """Live view of the shared partition so the settings form can show the user
    how much room they have before they pick a storage cap."""
    usage = shutil.disk_usage(STORAGE_BASE_PATH)
    stat = os.statvfs(STORAGE_BASE_PATH)
    return StorageInfoResponse(
        total_bytes=usage.total,
        free_bytes=usage.free,
        available_bytes=stat.f_bavail * stat.f_frsize,
        recordings_bytes=_dir_size(RECORDINGS_DIR),
        events_bytes=_dir_size(EVENT_FILES_DIR),
        min_free_floor_bytes=int(MIN_FREE_DISK_GB * _BYTES_PER_GB),
    )
