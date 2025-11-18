import os
from abc import ABC, abstractmethod
from onnxruntime import InferenceSession
import numpy as np
import requests
from pathlib import Path

from box import Box


class BasePromptEncoder(ABC):
    """
    Abstract base class for all embedding encoders (visual, text, etc.).
    """

    def __init__(
        self,
        config: Box,
        encoder_model_url: str,
        encoder_model_path: str,
    ):
        self._config: Box = config
        self._encoder_model_url: str = encoder_model_url
        self._encoder_model_path: str = encoder_model_path
        self._session: InferenceSession = None
        self._offset: int = None

    def _load_model(self) -> None:
        """Download and initialize the ONNX model."""
        path = self._download_file()
        self._session = InferenceSession(path)

    @abstractmethod
    def extract_embeddings(self, *args, **kwargs) -> np.ndarray:
        """Subclasses must implement modality-specific preprocessing and inference."""
        pass

    def _pad_and_quantize_features(self, features) -> np.ndarray:
        """
        Pad features to (1, 512, max_num_classes) and quantize if precision is int8.
        For FP16, return padded float16 features (no quantization).
        """
        num_padding = self._config.max_num_classes - features.shape[0]
        padded = np.pad(features, ((0, num_padding), (0, 0)), "constant").T.reshape(
            1, 512, self._config.max_num_classes
        )

        if self._config.precision == "fp16":
            return padded.astype(np.float16)

        quant = self._config.quant_values[self._config.name]
        out = (padded / quant["quant_scale"]) + quant["quant_zero_point"]
        return out.astype(np.uint8)

    def make_dummy(self) -> np.ndarray:
        """
        Create a dummy tensor of shape (1, 512, max_num_classes) for model input.
        For FP16, return zeros; for INT8, fill with the model's quantization zero point.
        """
        if self._config.precision == "fp16":
            return np.zeros((1, 512, self._config.max_num_classes), dtype=np.float16)
        qzp = int(
            round(
                self._config.quant_values.get(self._config.model_name, {}).get(
                    "quant_zero_point", 0
                )
            )
        )
        return np.full((1, 512, self._config.max_num_classes), qzp, dtype=np.uint8)

    def _download_file(self, url: str = "", path: str = "") -> Path:
        if url == "":
            url = self._encoder_model_url
        if path == "":
            path = self._encoder_model_path
        if not os.path.exists(path):
            with open(path, "wb") as f:
                f.write(requests.get(url).content)
        return path

    @property
    def offset(self) -> int:
        """Return class offset or encoder index limit."""
        return self._offset
