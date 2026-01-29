import base64
import logging
from typing import Callable, Optional

import cv2
import numpy as np

log = logging.getLogger(__name__)


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

    def fe_class_update(self, new_classes: list[str]) -> None:
        """Changes classes to detect based on user input."""
        if not new_classes or len(new_classes) == 0:
            log.info("List of new classes empty, skipping.")
            return
        self._update_classes(new_classes)
        log.info(f"Classes set to: {new_classes}")

    def fe_threshold_update(self, new_threshold: float) -> None:
        """Changes confidence threshold based on user input."""
        threshold = max(0.01, min(0.99, float(new_threshold)))
        self._set_threshold(threshold)
        log.info(f"Confidence threshold set to: {threshold}")

    def fe_image_upload(self, image_data: dict) -> None:
        """Handles image upload for visual prompting."""
        image = self._decode_image(image_data.get("data"))
        if image is None:
            log.info("Failed to decode uploaded image")
            return

        label = image_data.get("label") or image_data.get("filename", "object").split(".")[0]
        self._update_visual_prompt(image, [label], None)
        log.info(f"Image prompt set with label: {label}")

    def fe_bbox_prompt(self, payload: dict) -> dict:
        """Handles bounding box region selection for visual prompting."""
        # Try FE-provided image first, else fall back to cached live frame
        image = self._decode_image(payload.get("data")) if payload.get("data") else None
        if image is None:
            image = self._get_last_frame()
            if image is None:
                log.info("[BBox] No image data and no cached frame available")
                return {"ok": False, "reason": "no_image"}

        bbox = payload.get("bbox", {})
        bx = float(bbox.get("x", 0.0))
        by = float(bbox.get("y", 0.0))
        bw = float(bbox.get("width", 0.0))
        bh = float(bbox.get("height", 0.0))

        H, W = image.shape[:2]
        x0 = int(round(bx * W))
        y0 = int(round(by * H))
        x1 = int(round((bx + bw) * W))
        y1 = int(round((by + bh) * H))

        x0, x1 = sorted((x0, x1))
        y0, y1 = sorted((y0, y1))

        if x1 <= x0 or y1 <= y0:
            log.info("Invalid bbox, ignoring bbox prompt request.")
            return {"ok": False, "reason": "invalid_bbox"}

        # Build mask for the bbox region
        mask = np.zeros((H, W), dtype=np.float32)
        mask[y0:y1, x0:x1] = 1.0

        label = payload.get("label", "object")
        self._update_visual_prompt(image, [label], mask)
        log.info(f"BBox prompt set with label: {label}")
        return {"ok": True, "bbox": {"x0": x0, "y0": y0, "x1": x1, "y1": y1}}

    @staticmethod
    def _decode_image(data_uri: str) -> Optional[np.ndarray]:
        if not data_uri:
            return None
        try:
            base64_data = data_uri.split(",", 1)[1] if "," in data_uri else data_uri
            np_arr = np.frombuffer(base64.b64decode(base64_data), np.uint8)
            return cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        except Exception:
            return None
