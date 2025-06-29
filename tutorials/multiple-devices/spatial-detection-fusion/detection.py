import numpy as np


class Detection:
    def __init__(
        self, label: str, confidence: float, pos: np.ndarray, camera_friendly_id: int
    ):
        self.label = label
        self.confidence = confidence
        self.pos = pos
        self.corresponding_detections: list[Detection] = []
        self.camera_friendly_id = camera_friendly_id
