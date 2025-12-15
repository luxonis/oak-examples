from __future__ import annotations
from typing import Tuple
import numpy as np

from core.neural_network.prompts.encoders.textual_prompt_encoder import (
    TextualPromptEncoder,
)
from core.neural_network.prompts.handlers.base_prompt_handler import BasePromptHandler
from core.neural_network.prompts.front_end_prompt_services.payloads.class_update_payload import (
    ClassUpdatePayload,
)


class TextPromptHandler(BasePromptHandler):
    """Handles embedding extraction and label synchronization for class name updates."""

    def __init__(self, encoder: TextualPromptEncoder):
        super().__init__(encoder)
        self._payload: ClassUpdatePayload = None

    def process(self, payload: ClassUpdatePayload) -> Tuple[np.ndarray, np.ndarray]:
        self._class_names = payload.classes
        embeddings = self._encoder.extract_embeddings(self.get_class_names())
        dummy = self._encoder.make_dummy()

        return embeddings, dummy
