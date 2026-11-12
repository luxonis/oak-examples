from pathlib import Path

from config import STORAGE_BASE_PATH

EVENT_FILES_DIR = Path(STORAGE_BASE_PATH) / "events"
_RESOLVED_EVENT_FILES_DIR = EVENT_FILES_DIR.resolve()


def resolve_event_file_path(relative_path: str) -> Path:
    requested_path = Path(relative_path)
    if requested_path.is_absolute():
        raise FileNotFoundError("Absolute event file paths are not allowed")

    resolved_path = (EVENT_FILES_DIR / requested_path).resolve()
    try:
        resolved_path.relative_to(_RESOLVED_EVENT_FILES_DIR)
    except ValueError as exc:
        raise FileNotFoundError(
            "Event file path escapes the event files directory"
        ) from exc

    return resolved_path
