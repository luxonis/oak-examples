from typing import TypedDict


class BBox(TypedDict):
    x: float
    y: float
    width: float
    height: float


class BBoxPromptPayload(TypedDict):
    """Payload for bounding box prompts"""

    bbox: BBox
