from pathlib import Path

from config import STORAGE_BASE_PATH

RECORDINGS_DIR = Path(STORAGE_BASE_PATH) / "recordings"
_RESOLVED_RECORDINGS_DIR = RECORDINGS_DIR.resolve()


def resolve_recording_file_path(relative_path: str) -> Path:
    requested_path = Path(relative_path)
    if requested_path.is_absolute():
        raise FileNotFoundError("Absolute recording file paths are not allowed")

    resolved_path = (RECORDINGS_DIR / requested_path).resolve()
    try:
        resolved_path.relative_to(_RESOLVED_RECORDINGS_DIR)
    except ValueError as exc:
        raise FileNotFoundError(
            "Recording file path escapes the recordings directory"
        ) from exc

    return resolved_path
