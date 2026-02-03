from typing import Optional

from box import Box
import cv2
import numpy as np

from .base_prompt_encoder import BasePromptEncoder


class VisualPromptEncoder(BasePromptEncoder):
    """
    Handles visual embedding extraction using a visual encoder.
    Supports both YOLOE and YOLO-World visual encoders.
    """

    def __init__(
        self,
        config: Box,
        model_name: str,
        precision: str,
    ):
        quant_key = "yoloe-image" if model_name == "yoloe" else "yolo-world"
        super().__init__(
            config,
            config.paths.visual_encoder.slug,
            config.paths.visual_encoder.path,
            model_name,
            precision,
            quant_key=quant_key,
        )
        self._offset: int = config.visual_offset

    def extract_embeddings(
        self, image: np.ndarray, mask_prompt: Optional[np.ndarray] = None
    ) -> np.ndarray:
        """Extract visual embeddings from an image."""
        self._load_model()

        if self._model_name == "yolo-world":
            embeddings = self._extract_yolo_world(image)
        else:
            embeddings = self._extract_yoloe(image, mask_prompt)

        image_features = self._pad_and_quantize_features(embeddings)
        del self._session
        return image_features

    def _extract_yoloe(
        self, image: np.ndarray, mask_prompt: Optional[np.ndarray]
    ) -> np.ndarray:
        """YOLOE visual encoding."""
        prompts = self._build_mask_prompt(mask_prompt)

        image_resized = cv2.resize(image, (640, 640))
        image_array = image_resized.astype(np.float32) / 255.0
        image_array = np.transpose(image_array, (2, 0, 1))
        input_tensor = np.expand_dims(image_array, axis=0).astype(np.float32)

        outputs = self._session.run(None, {"images": input_tensor, "prompts": prompts})
        return outputs[0].squeeze(0).reshape(1, -1)

    def _extract_yolo_world(self, image: np.ndarray) -> np.ndarray:
        """YOLO-World visual encoding."""
        image_resized = cv2.resize(image, (224, 224))
        image_array = image_resized.astype(np.float32) / 255.0

        mean = np.array([0.48145466, 0.4578275, 0.40821073], dtype=np.float32)
        std = np.array([0.26862954, 0.26130258, 0.27577711], dtype=np.float32)
        image_array = (image_array - mean) / std

        image_array = np.transpose(image_array, (2, 0, 1))
        input_tensor = np.expand_dims(image_array, axis=0).astype(np.float32)

        input_name = self._session.get_inputs()[0].name
        outputs = self._session.run(None, {input_name: input_tensor})
        return outputs[0].squeeze(0).reshape(1, -1)

    def _build_mask_prompt(self, mask_prompt: Optional[np.ndarray]) -> np.ndarray:
        """Build the 80x80 mask prompt for YOLOE visual encoder."""
        if mask_prompt is None:
            # Default - center region mask
            prompts = np.zeros((1, 1, 80, 80), dtype=np.float32)
            prompts[0, 0, 5:75, 5:75] = 1.0
            return prompts

        prompts = np.asarray(mask_prompt, dtype=np.float32)
        if prompts.ndim == 2:
            if prompts.shape != (80, 80):
                prompts = cv2.resize(prompts, (80, 80), interpolation=cv2.INTER_NEAREST)
            prompts = prompts[None, None, :, :]
        elif prompts.shape == (1, 1, 80, 80):
            pass
        else:
            raise ValueError("mask_prompt must have shape (80,80) or (1,1,80,80)")

        return prompts
