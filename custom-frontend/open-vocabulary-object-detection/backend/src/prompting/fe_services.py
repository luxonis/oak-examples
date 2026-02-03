import base64
import logging
from typing import Callable, Optional

import cv2
import numpy as np

log = logging.getLogger(__name__)


class PromptingFEServices:
    """
    Groups all frontend service handlers for prompt-based detection.

    Services:
        - fe_class_update: Update text-based detection classes
        - fe_threshold_update: Update confidence threshold
        - fe_image_upload: Upload image for visual prompting
        - fe_bbox_prompt: Select region via bounding box for visual prompting
        - fe_rename_image_prompt: Rename an existing image prompt
        - fe_delete_image_prompt: Delete an existing image prompt
    """

    def __init__(
        self,
        update_classes: Callable[[list[str]], None],
        add_image_prompt: Callable[[np.ndarray, str, Optional[np.ndarray]], None],
        add_bbox_prompt: Callable[[np.ndarray, str, int, int, int, int], None],
        rename_image_prompt: Callable[
            [Optional[int], Optional[str], Optional[str]], bool
        ],
        delete_image_prompt: Callable[[Optional[int], Optional[str]], bool],
        set_confidence_threshold: Callable[[float], None],
        get_last_frame: Callable[[], Optional[np.ndarray]],
        max_num_classes: int = 80,
    ):
        self._update_classes = update_classes
        self._add_image_prompt = add_image_prompt
        self._add_bbox_prompt = add_bbox_prompt
        self._rename_image_prompt = rename_image_prompt
        self._delete_image_prompt = delete_image_prompt
        self._set_threshold = set_confidence_threshold
        self._get_last_frame = get_last_frame

    def fe_class_update(self, new_classes: list[str]) -> None:
        """Update detection classes."""
        if not new_classes:
            log.warning("Class update called with empty list, skipping.")
            return

        self._update_classes(new_classes)
        log.info(f"Classes updated: {new_classes}")

    def fe_threshold_update(self, new_threshold: float) -> None:
        """Update detection confidence threshold."""
        threshold = max(0.01, min(0.99, float(new_threshold)))
        self._set_threshold(threshold)
        log.info(f"Confidence threshold updated: {threshold:.2f}")

    def fe_image_upload(self, payload: dict) -> None:
        """
        Handle image upload for visual prompting.

        Args:
            payload: Dict with 'data' (base64), 'filename', and optional 'label'.
        """
        data = payload.get("data")
        if not data:
            log.error("Image upload missing 'data' field")
            return

        image = self._decode_image(data)
        if image is None:
            log.error("Failed to decode uploaded image")
            return

        filename = payload.get("filename", "image.png")
        label = payload.get("label") or filename.rsplit(".", 1)[0]
        self._add_image_prompt(image=image, label=label, mask=None)

        log.info(f"Image prompt added with label: {label}")

    def fe_bbox_prompt(self, payload: dict) -> dict:
        """
        Handle bounding box region selection for visual prompting.

        Args:
            payload: Dict with 'bbox' (x, y, width, height), optional 'data', and 'label'.
        """
        bbox = payload.get("bbox", {})
        if not bbox:
            log.error("BBox prompt missing 'bbox' field")
            return {"ok": False, "reason": "missing_bbox"}

        image = None
        if payload.get("data"):
            image = self._decode_image(payload["data"])
        if image is None:
            image = self._get_last_frame()
        if image is None:
            log.warning("No image available for bbox prompt")
            return {"ok": False, "reason": "no_image"}

        H, W = image.shape[:2]
        bx = float(bbox.get("x", 0.0))
        by = float(bbox.get("y", 0.0))
        bw = float(bbox.get("width", 0.0))
        bh = float(bbox.get("height", 0.0))

        x0 = int(round(bx * W))
        y0 = int(round(by * H))
        x1 = int(round((bx + bw) * W))
        y1 = int(round((by + bh) * H))

        x0, x1 = sorted((max(0, x0), min(W, x1)))
        y0, y1 = sorted((max(0, y0), min(H, y1)))

        if x1 <= x0 or y1 <= y0:
            log.warning(f"Invalid bbox dimensions: ({x0}, {y0}) to ({x1}, {y1})")
            return {"ok": False, "reason": "invalid_bbox"}

        label = payload.get("label", "object")
        self._add_bbox_prompt(image, label, x0, y0, x1, y1)

        log.info(f"BBox prompt added: label='{label}', region=({x0},{y0})-({x1},{y1})")

        return {"ok": True, "bbox": {"x0": x0, "y0": y0, "x1": x1, "y1": y1}}

    def fe_rename_image_prompt(self, payload: dict) -> dict:
        """
        Rename an existing stored image prompt.

        Args:
            payload: Dict with 'index' or 'oldLabel', and 'newLabel'.
        """
        index = payload.get("index")
        old_label = payload.get("oldLabel")
        new_label = payload.get("newLabel")

        if not new_label:
            log.warning("Rename image prompt: new_label is required")
            return {"ok": False, "reason": "new_label_required"}

        success = self._rename_image_prompt(index, old_label, new_label)
        if success:
            log.info(f"Image prompt renamed to '{new_label}'")
            return {"ok": True}
        else:
            log.warning("Rename image prompt: index/old_label not found")
            return {"ok": False, "reason": "not_found"}

    def fe_delete_image_prompt(self, payload: dict) -> dict:
        """
        Delete an existing image prompt.

        Args:
            payload: Dict with 'index' or 'label'.
        """
        index = payload.get("index")
        label = payload.get("label")

        if index is None and label is None:
            log.warning("Delete image prompt: index or label is required")
            return {"ok": False, "reason": "index_or_label_required"}

        success = self._delete_image_prompt(index, label)
        if success:
            log.info(f"Image prompt deleted (index={index}, label={label})")
            return {"ok": True}
        else:
            log.warning("Delete image prompt: index/label not found")
            return {"ok": False, "reason": "not_found"}

    @staticmethod
    def _decode_image(data_uri: str) -> Optional[np.ndarray]:
        if not data_uri:
            return None
        try:
            base64_data = data_uri.split(",", 1)[1] if "," in data_uri else data_uri
            image_bytes = base64.b64decode(base64_data)
            np_arr = np.frombuffer(image_bytes, dtype=np.uint8)
            return cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        except Exception as e:
            log.debug(f"Image decode failed: {e}")
            return None
