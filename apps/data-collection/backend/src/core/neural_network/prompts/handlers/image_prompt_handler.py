import base64
import cv2
import numpy as np

from core.neural_network.prompts.encoders.visual_prompt_encoder import (
    VisualPromptEncoder,
)
from core.neural_network.prompts.handlers.base_prompt_handler import BasePromptHandler
from core.neural_network.prompts.front_end_prompt_services.payloads.image_upload_payload import (
    ImageUploadPayload,
)


class ImagePromptHandler(BasePromptHandler):
    """
    Handles full image prompt preparation flow:
    decode base64 → preprocess → extract visual embeddings → prepare dummy features.
    """

    def __init__(self, encoder: VisualPromptEncoder):
        super().__init__(encoder)
        self._payload: ImageUploadPayload = None

    def process(self, payload: ImageUploadPayload) -> tuple[np.ndarray, np.ndarray]:
        """Decode and process uploaded image payload into model-ready features."""
        self._payload = payload
        self._class_names = [self._payload.filename.split(".")[0]]
        image = self._decode_image()
        embeddings = self._encoder.extract_embeddings(image)
        dummy = self._encoder.make_dummy()
        return embeddings, dummy

    def _decode_image(self) -> np.ndarray:
        """Convert base64-encoded image to OpenCV array."""
        data_uri = self._payload.data
        if "," in data_uri:
            _, base64_data = data_uri.split(",", 1)
        else:
            base64_data = data_uri
        np_arr = np.frombuffer(base64.b64decode(base64_data), np.uint8)
        return cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
