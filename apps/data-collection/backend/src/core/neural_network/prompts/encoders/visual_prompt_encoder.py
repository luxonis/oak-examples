import cv2
import numpy as np
from box import Box

from core.neural_network.prompts.encoders.base_prompt_encoder import BasePromptEncoder


class VisualPromptEncoder(BasePromptEncoder):
    """
    Handles visual embedding extraction using a visual encoder.

    Loads an ONNX visual encoder, preprocesses an image input, performs
    forward inference, and returns quantized visual feature tensors
    compatible with downstream models.
    """

    def __init__(
        self,
        config: Box,
    ):
        super().__init__(
            config,
            config.paths.visual_encoder.url,
            config.paths.visual_encoder.path,
        )
        self._offset: str = config.visual_offset

    def extract_embeddings(self, image: np.ndarray, mask_prompt=None) -> np.ndarray:
        self._load_model()
        if mask_prompt is None:
            prompts = np.zeros((1, 1, 80, 80), dtype=np.float32)
            prompts[0, 0, 5:75, 5:75] = 1.0
        else:
            prompts = np.asarray(mask_prompt, dtype=np.float32)
            if prompts.ndim == 2:
                if prompts.shape != (80, 80):
                    prompts = cv2.resize(
                        prompts, (80, 80), interpolation=cv2.INTER_NEAREST
                    )
                prompts = prompts[None, None, :, :]
            elif prompts.shape == (1, 1, 80, 80):
                pass
            else:
                raise ValueError("mask_prompt must have shape (80,80) or (1,1,80,80)")

        image_resized = cv2.resize(image, (640, 640))
        image_array = image_resized.astype(np.float32) / 255.0
        image_array = np.transpose(image_array, (2, 0, 1))
        input_tensor = np.expand_dims(image_array, axis=0).astype(np.float32)

        outputs = self._session.run(None, {"images": input_tensor, "prompts": prompts})

        image_embeddings = outputs[0].squeeze(0).reshape(1, -1)
        image_features = self._pad_and_quantize_features(image_embeddings)

        del self._session

        return image_features
