from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List, Tuple, TypedDict
import numpy as np

from core.neural_network.prompts.encoders.base_prompt_encoder import BasePromptEncoder


class BasePromptHandler(ABC):
    """
    Abstract base handler for converting various input modalities
    (image, text, bbox, etc.) into model-ready prompts.
    """

    def __init__(self, encoder: BasePromptEncoder):
        self._encoder = encoder
        self._class_names: List[str] = []

    @abstractmethod
    def process(self, payload: TypedDict) -> Tuple[np.ndarray, np.ndarray]:
        """
        Transform input (payload, image, bbox, etc.) into model-ready tensors.
        Must return (embeddings, dummy) tuple.
        """
        raise NotImplementedError

    def get_class_names(self) -> List[str]:
        """Return list of class names associated with the processed data."""
        return self._class_names

    def get_offset(self) -> int:
        """Return class offset or encoder index limit."""
        return self._encoder.offset
