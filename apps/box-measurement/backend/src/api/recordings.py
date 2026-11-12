import logging
import re
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from util.recording_files import RECORDINGS_DIR, resolve_recording_file_path

logger = logging.getLogger(__name__)

# recording-YYYYmmddTHHMMSSffffffZ.mp4
_FILENAME_TIMESTAMP = re.compile(r"^recording-(\d{8}T\d{12})Z\.mp4$")


def _parse_chunk_start(filename: str) -> datetime | None:
    match = _FILENAME_TIMESTAMP.match(filename)
    if match is None:
        return None
    try:
        return datetime.strptime(match.group(1), "%Y%m%dT%H%M%S%f").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return None


class RecordingResponse(BaseModel):
    filename: str
    started_at: datetime
    ended_at: datetime
    size_bytes: int


class GetRecordingsResponse(BaseModel):
    recordings: list[RecordingResponse]


class EmptyRequest(BaseModel):
    pass


class GetRecordingFileRequest(BaseModel):
    filename: str = Field(min_length=1)


def get_recordings(request: EmptyRequest) -> GetRecordingsResponse:
    """Lists all retained (finalized) recording chunks, newest first.

    Retention is enforced by the storage-size cap (RecordingCleaner), so every
    chunk still on disk is shown — there is no separate time-based filter."""
    if not RECORDINGS_DIR.is_dir():
        return GetRecordingsResponse(recordings=[])

    recordings: list[RecordingResponse] = []
    for path in RECORDINGS_DIR.glob("recording-*.mp4"):
        started_at = _parse_chunk_start(path.name)
        if started_at is None:
            continue
        stat = path.stat()
        recordings.append(
            RecordingResponse(
                filename=path.name,
                started_at=started_at,
                ended_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
                size_bytes=stat.st_size,
            )
        )

    recordings.sort(key=lambda r: r.started_at, reverse=True)
    return GetRecordingsResponse(recordings=recordings)


def get_recording_file(request: GetRecordingFileRequest) -> bytes | None:
    try:
        return resolve_recording_file_path(request.filename).read_bytes()
    except FileNotFoundError:
        logger.warning("Recording file is unavailable: %s", request.filename)
        return None
    except OSError:
        logger.exception("Error reading recording file %s", request.filename)
        return None
