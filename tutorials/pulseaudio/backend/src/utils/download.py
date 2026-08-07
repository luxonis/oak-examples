import base64
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

RECORDINGS_DIR = Path("/data/recordings")
RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)


def list_recordings_service(_: Any | None = None) -> dict:
    files = sorted((p.name for p in RECORDINGS_DIR.glob("*.wav")), reverse=True)
    return {"ok": True, "files": files}


def download_recording_service(payload: dict | None = None) -> dict:
    filename = (payload or {}).get("filename")
    if not isinstance(filename, str):
        return {"ok": False, "error": "Missing filename"}

    path = (RECORDINGS_DIR / Path(filename).name).resolve()

    if path.parent != RECORDINGS_DIR or not path.is_file():
        return {"ok": False, "error": f"File not found: {filename}"}

    try:
        data = path.read_bytes()
    except Exception as e:
        logger.exception("Failed reading recording: %s", filename)
        return {"ok": False, "error": f"Failed to read file: {e}"}

    return {
        "ok": True,
        "filename": path.name,
        "mime": "audio/wav",
        "b64": base64.b64encode(data).decode(),
        "size": len(data),
    }
