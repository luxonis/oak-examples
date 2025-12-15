import numpy as np

from core.neural_network.prompts.encoders.visual_prompt_encoder import (
    VisualPromptEncoder,
)
from core.neural_network.prompts.handlers.base_prompt_handler import BasePromptHandler
from core.neural_network.prompts.frame_cache_node import FrameCacheNode
from core.neural_network.prompts.front_end_prompt_services.payloads.bbox_prompt_payload import (
    BBoxPromptPayload,
)


class BBoxPromptHandler(BasePromptHandler):
    """
    Handles extraction of embeddings for a specific bounding-box region.
    Takes an image and a bounding box (normalized coordinates) and produces
    model-ready visual embeddings with a dummy tensor.
    """

    def __init__(self, encoder: VisualPromptEncoder, frame_cache: FrameCacheNode):
        super().__init__(encoder)
        self._frame_cache: FrameCacheNode = frame_cache
        self._image: np.ndarray = None
        self._bbox: BBoxPromptPayload = None
        self._class_names: list[str] = ["Bounding Box Object"]

    def process(self, payload: BBoxPromptPayload) -> tuple[np.ndarray, np.ndarray]:
        """Crop region mask based on bbox and extract embeddings."""
        self._image = self._frame_cache.get_last_frame()
        self._bbox = payload

        mask = self._make_mask()
        embeddings = self._encoder.extract_embeddings(self._image, mask)
        dummy = self._encoder.make_dummy()

        return embeddings, dummy

    def _make_mask(self) -> np.ndarray:
        """Build a binary mask corresponding to the provided bounding box."""
        H, W = self._image.shape[:2]
        bx, by, bw, bh = (
            self._bbox.x,
            self._bbox.y,
            self._bbox.width,
            self._bbox.height,
        )

        x0, y0 = int(bx * W), int(by * H)
        x1, y1 = int((bx + bw) * W), int((by + bh) * H)
        x0, x1 = sorted((x0, x1))
        y0, y1 = sorted((y0, y1))

        if x1 <= x0 or y1 <= y0:
            raise ValueError(f"Invalid bbox coordinates: {(x0, y0, x1, y1)}")

        mask = np.zeros((H, W), dtype=np.float32)
        mask[y0:y1, x0:x1] = 1.0
        return mask
