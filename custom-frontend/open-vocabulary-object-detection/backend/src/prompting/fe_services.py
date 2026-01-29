import base64
from typing import Callable, Optional

import cv2
import numpy as np
from pydantic import ValidationError

from .payloads import (
    ClassUpdatePayload,
    ThresholdUpdatePayload,
    ImageUploadPayload,
    BBoxPromptPayload,
)


class PromptingFEServices:
    """Groups all FE handlers related to prompting."""

    def __init__(
        self,
        update_classes: Callable[[list[str]], None],
        update_visual_prompt: Callable[
            [np.ndarray, list[str], Optional[np.ndarray]], None
        ],
        set_confidence_threshold: Callable[[float], None],
        get_last_frame: Callable[[], Optional[np.ndarray]],
    ):
        self._update_classes = update_classes
        self._update_visual_prompt = update_visual_prompt
        self._set_threshold = set_confidence_threshold
        self._get_last_frame = get_last_frame

    def fe_class_update(self, payload: dict) -> dict:
        try:
            validated = ClassUpdatePayload.model_validate(payload)
        except ValidationError as e:
            return {"ok": False, "error": e.errors()}

        self._update_classes(validated.classes)
        return {"ok": True, "classes": validated.classes}

    def fe_threshold_update(self, payload: dict) -> dict:
        try:
            validated = ThresholdUpdatePayload.model_validate(payload)
        except ValidationError as e:
            return {"ok": False, "error": e.errors()}

        self._set_threshold(validated.threshold)
        return {"ok": True, "threshold": float(validated.threshold)}

    def fe_image_upload(self, payload: dict) -> dict:
        try:
            validated = ImageUploadPayload.model_validate(payload)
        except ValidationError as e:
            return {"ok": False, "error": e.errors()}

        class_name = validated.filename.rsplit(".", 1)[0]
        image = self._decode_image(validated.data)
        if image is None:
            return {"ok": False, "error": "Invalid image data"}

        self._update_visual_prompt(image, [class_name], None)
        return {"ok": True, "classes": class_name}

    def fe_bbox_prompt(self, payload: dict) -> dict:
        try:
            validated = BBoxPromptPayload.model_validate(payload)
        except ValidationError as e:
            return {"ok": False, "error": e.errors()}

        image = self._get_last_frame()
        if image is None:
            return {"ok": False, "error": "No frame available"}

        mask = self._make_bbox_mask(image, validated)
        if mask is None:
            return {"ok": False, "error": "Invalid bbox"}

        self._update_visual_prompt(image, ["Selected Region"], mask)
        return {"ok": True, "classes": ["Selected Region"]}

    @staticmethod
    def _make_bbox_mask(
        image: np.ndarray, bbox: BBoxPromptPayload
    ) -> np.ndarray | None:
        H, W = image.shape[:2]
        x0 = int(bbox.x * W)
        y0 = int(bbox.y * H)
        x1 = int((bbox.x + bbox.width) * W)
        y1 = int((bbox.y + bbox.height) * H)

        x0 = max(0, min(W, x0))
        x1 = max(0, min(W, x1))
        y0 = max(0, min(H, y0))
        y1 = max(0, min(H, y1))

        if x1 <= x0 or y1 <= y0:
            return None

        mask = np.zeros((H, W), dtype=np.float32)
        mask[y0:y1, x0:x1] = 1.0
        return mask

    @staticmethod
    def _decode_image(data_uri: str) -> np.ndarray | None:
        try:
            base64_data = data_uri.split(",", 1)[1] if "," in data_uri else data_uri
            np_arr = np.frombuffer(base64.b64decode(base64_data), np.uint8)
            return cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        except Exception:
            return None
