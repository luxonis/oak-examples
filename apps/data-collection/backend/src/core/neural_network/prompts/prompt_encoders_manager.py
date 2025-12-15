import numpy as np
from box import Box

from core.neural_network.prompts.encoders.base_prompt_encoder import BasePromptEncoder
from core.neural_network.prompts.encoders.textual_prompt_encoder import (
    TextualPromptEncoder,
)
from core.neural_network.prompts.encoders.visual_prompt_encoder import (
    VisualPromptEncoder,
)


class PromptEncodersManager:
    """
    Central manager for initializing and caching encoder components.
    """

    def __init__(self, config: Box):
        self._model_config = config

        self.textual_encoder: BasePromptEncoder = None
        self.visual_encoder: BasePromptEncoder = None

        self.text_prompt: np.ndarray = None
        self.image_prompt: np.ndarray = None

    def build(self):
        self.textual_encoder = self._init_textual_encoder()
        self.visual_encoder = self._init_visual_encoder()

    def _init_textual_encoder(self) -> TextualPromptEncoder:
        return TextualPromptEncoder(self._model_config)

    def _init_visual_encoder(self) -> VisualPromptEncoder:
        return VisualPromptEncoder(self._model_config)

    def prepare_initial_prompts(self) -> tuple[np.ndarray, np.ndarray]:
        text_prompt = self.textual_encoder.extract_embeddings(
            self._model_config.class_names
        )
        image_prompt = self.textual_encoder.make_dummy()
        return text_prompt, image_prompt
