"""Fair, bounded decision scheduling independent of DepthAI and llama.cpp."""

import math


def validate_refresh(value):
    if (
        type(value) not in (int, float)
        or not math.isfinite(value)
        or not 0.5 <= value <= 30
    ):
        raise ValueError("Capture interval must be between 0.5 and 30 seconds.")
    return float(value)


def choose_detection(detections, tracks):
    """Prefer an unseen object, then the least recently evaluated object.

    Args:
        detections: Observations paired with one captured frame.
        tracks: Current tracks holding each object's last inference time.

    Returns:
        The next detection to evaluate, or ``None`` if the batch is empty.
    """
    return min(
        detections,
        key=lambda obs: (
            tracks.get(obs["id"], {}).get("last_started", 0) != 0,
            tracks.get(obs["id"], {}).get("last_started", 0),
            obs["id"],
        ),
        default=None,
    )


def pixel_box(box, width, height):
    """Clip a normalized detection box to pixel bounds for a valid crop.

    Returns:
        Pixel coordinates or ``None`` for a crop smaller than 16 pixels.
    """
    if len(box) != 4 or any(not math.isfinite(v) for v in box):
        return None
    x0 = max(0, min(width, math.floor(box[0] * width)))
    y0 = max(0, min(height, math.floor(box[1] * height)))
    x1 = max(0, min(width, math.ceil(box[2] * width)))
    y1 = max(0, min(height, math.ceil(box[3] * height)))
    if x1 - x0 < 16 or y1 - y0 < 16:
        return None
    return x0, y0, x1, y1
