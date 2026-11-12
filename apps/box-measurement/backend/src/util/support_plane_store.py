import json
import logging
import math
from pathlib import Path

from solutions_sdk.box_measurement import SupportPlane

from config import STORAGE_BASE_PATH

logger = logging.getLogger(__name__)

SUPPORT_PLANE_FILE = Path(STORAGE_BASE_PATH) / "support_plane.json"


def save_plane(plane: SupportPlane, distance_offset_mm: float = 0.0) -> None:
    """Persist geometry and application correction; failures reach the service caller.

    Saving is separate from activation. An error does not undo an active plane.
    """
    if not math.isfinite(distance_offset_mm):
        raise ValueError("Support-plane distance correction must be finite")
    SUPPORT_PLANE_FILE.parent.mkdir(parents=True, exist_ok=True)
    SUPPORT_PLANE_FILE.write_text(
        json.dumps(
            {
                "support_plane": plane.toJson(),
                "distance_offset_mm": distance_offset_mm,
            },
            allow_nan=False,
        ),
        encoding="utf-8",
    )


def load_plane() -> tuple[SupportPlane, float] | None:
    """Return new-format geometry, rejecting legacy calibrations and corrections."""
    if not SUPPORT_PLANE_FILE.exists():
        return None
    try:
        data = json.loads(SUPPORT_PLANE_FILE.read_text(encoding="utf-8"))
        plane = SupportPlane.fromJson(data["support_plane"])
        distance_offset_mm = float(data["distance_offset_mm"])
        if not math.isfinite(distance_offset_mm):
            raise ValueError("Saved distance correction must be finite")
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        logger.warning(
            "Saved support plane is unavailable or incompatible; recalibration required"
        )
        return None
    return plane, distance_offset_mm


def clear_plane() -> None:
    """Drops the saved plane so the next start recalibrates."""
    SUPPORT_PLANE_FILE.unlink(missing_ok=True)
