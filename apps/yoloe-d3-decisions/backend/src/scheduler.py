"""Fair, bounded decision scheduling independent of DepthAI and llama.cpp."""

import math


def validate_refresh(value):
    if (
        type(value) not in (int, float)
        or not math.isfinite(value)
        or not 0.5 <= value <= 30
    ):
        raise ValueError("Target refresh must be between 0.5 and 30 seconds.")
    return float(value)


def box_iou(a, b):
    left, top = max(a[0], b[0]), max(a[1], b[1])
    right, bottom = min(a[2], b[2]), min(a[3], b[3])
    intersection = max(0, right - left) * max(0, bottom - top)
    area_a = max(0, a[2] - a[0]) * max(0, a[3] - a[1])
    area_b = max(0, b[2] - b[0]) * max(0, b[3] - b[1])
    union = area_a + area_b - intersection
    return intersection / union if union > 0 else 0.0


def match_observations(tracks, observations, now, next_id, threshold=0.25):
    """Assign stable IDs by class and box overlap without a device tracker.

    Args:
        tracks: Current tracked objects keyed by ID.
        observations: YOLO-E detections from one frame.
        now: Monotonic time of that frame.
        next_id: ID available for a new object.
        threshold: Minimum overlap for reusing an ID.

    Returns:
        The matched observations and the next available ID.
    """
    used = set()
    matched = []
    for obs in sorted(observations, key=lambda item: item["confidence"], reverse=True):
        candidates = (
            (box_iou(obs["box"], track["box"]), track_id)
            for track_id, track in tracks.items()
            if track_id not in used
            and now - track["seen"] < 1.5
            and track["label"] == obs["label"]
        )
        overlap, track_id = max(candidates, default=(0.0, -1))
        if overlap < threshold:
            track_id = next_id
            next_id += 1
        used.add(track_id)
        matched.append({**obs, "id": track_id})
    return matched, next_id


def choose_track(tracks, now, refresh):
    """Choose an unseen track first, then the stalest due track.

    Tracks are current observations only. There is no image or request queue.

    Args:
        tracks: Current tracked objects keyed by ID.
        now: Current monotonic time.
        refresh: Minimum time between decisions for one object.

    Returns:
        The selected due track, or ``None`` if none is due.
    """
    due = [
        track
        for track in tracks.values()
        if now - track["seen"] < 1.5 and now - track["last_started"] >= refresh
    ]
    if not due:
        return None
    return min(
        due,
        key=lambda track: (
            track["last_started"] != 0,
            track["last_started"],
            track["id"],
        ),
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
