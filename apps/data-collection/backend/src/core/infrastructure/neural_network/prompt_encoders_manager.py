import numpy as np
from box import Box

from core.encoders.textual_prompt_encoder import TextualPromptEncoder
from core.encoders.visual_prompt_encoder import VisualPromptEncoder


class PromptEncodersManager:
    """
    Central manager for initializing and caching encoder components.
    """

    def __init__(self, config: Box):
        self._model_config = config

        self.textual_encoder = self._init_textual_encoder()
        self.visual_encoder = self._init_visual_encoder()

        self.text_prompt, self.image_prompt = self._prepare_initial_prompts()

    def _init_textual_encoder(self) -> TextualPromptEncoder:
        return TextualPromptEncoder(config=self._model_config)

    def _init_visual_encoder(self) -> VisualPromptEncoder:
        return VisualPromptEncoder(config=self._model_config)

    def _prepare_initial_prompts(self) -> tuple[np.ndarray, np.ndarray]:
        text_prompt = self.textual_encoder.extract_embeddings(
            self._model_config.class_names
        )
        image_prompt = self.textual_encoder.make_dummy()
        return text_prompt, image_prompt
