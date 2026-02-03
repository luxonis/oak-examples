import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from box import Box
from onnxruntime import InferenceSession
from tqdm import tqdm
import numpy as np
import requests


HUBAI_API_BASE = "https://easyml.cloud.luxonis.com/models/api/v1"


class BasePromptEncoder(ABC):
    """
    Abstract base class for all embedding encoders (visual, text, etc.).
    """

    def __init__(
        self,
        config: Box,
        encoder_model_slug: str,
        encoder_model_path: str,
        model_name: str,
        precision: str,
        quant_key: Optional[str] = None,
    ):
        self._config: Box = config
        self._encoder_model_slug: str = encoder_model_slug
        self._encoder_model_path: str = encoder_model_path
        self._model_name: str = model_name
        self._precision: str = precision
        self._quant_key = quant_key or model_name
        self._session: InferenceSession = None
        self._offset: int = None

    def _load_model(self) -> None:
        """Download from HubAI and initialize the ONNX model."""
        path = self._download_from_hubai(
            self._encoder_model_slug, self._encoder_model_path
        )
        self._session = InferenceSession(str(path))

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

        if self._precision == "fp16":
            return padded.astype(np.float16)

        quant = self._config.quant_values[self._quant_key]
        out = (padded / quant["quant_scale"]) + quant["quant_zero_point"]
        return out.astype(np.uint8)

    def make_dummy(self) -> np.ndarray:
        """
        Create a dummy tensor of shape (1, 512, max_num_classes) for model input.
        For FP16, return zeros; for INT8, fill with the model's quantization zero point.
        """
        if self._precision == "fp16":
            return np.zeros((1, 512, self._config.max_num_classes), dtype=np.float16)
        qzp = int(
            round(
                self._config.quant_values.get(self._quant_key, {}).get(
                    "quant_zero_point", 0
                )
            )
        )
        return np.full((1, 512, self._config.max_num_classes), qzp, dtype=np.uint8)

    def _download_from_hubai(self, model_slug: str, local_filename: str) -> Path:
        """
        Download an ONNX model from HubAI.
        """
        if os.path.exists(local_filename):
            return Path(local_filename)

        model_name_slug = model_slug.split("/")[-1].split(":")[0]
        model_variant_slug = model_slug.split("/")[-1].split(":")[1]

        model_res = requests.get(
            f"{HUBAI_API_BASE}/models",
            params={"slug": model_name_slug, "is_public": True},
        )
        model_id = model_res.json()[0]["id"]

        variant_res = requests.get(
            f"{HUBAI_API_BASE}/modelVersions",
            params={
                "model_id": model_id,
                "variant_slug": model_variant_slug,
                "is_public": True,
            },
        )
        model_variant_id = variant_res.json()[0]["id"]

        download_res = requests.get(
            f"{HUBAI_API_BASE}/modelVersions/{model_variant_id}/download",
        )
        download_link = download_res.json()[0]["download_link"]

        self._download_file(download_link, local_filename)

        return Path(local_filename)

    def _download_file(self, url: str, local_filename: str) -> Path:
        """Download a file from a URL."""
        if os.path.exists(local_filename):
            return Path(local_filename)

        with requests.get(url, stream=True) as r:
            r.raise_for_status()

            total_size = int(r.headers.get("content-length", 0))
            block_size = 8192  # 8KB chunks
            progress_bar = tqdm(
                total=total_size, unit="iB", unit_scale=True, desc=local_filename
            )

            with open(local_filename, "wb") as f:
                for chunk in r.iter_content(chunk_size=block_size):
                    if chunk:
                        f.write(chunk)
                        progress_bar.update(len(chunk))
            progress_bar.close()

        return Path(local_filename)

    @property
    def offset(self) -> int:
        """Return class offset or encoder index limit."""
        return self._offset

    @property
    def max_num_classes(self) -> int:
        return int(self._config.max_num_classes)
