import logging
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

log = logging.getLogger(__name__)


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
        quant_key: str = None,
    ):
        self._config: Box = config
        self._encoder_model_slug: str = encoder_model_slug
        self._encoder_model_path: str = encoder_model_path
        self._model_name: str = model_name
        self._precision: str = precision
        self._quant_key: str = quant_key or model_name
        self._session: InferenceSession = None
        self._offset: int = None
        self._on_npu: bool = False
        self._batch_bucket: Optional[int] = None

    def _load_model(self) -> None:
        """Download from HubAI and initialize the ONNX model."""
        path = self._download_from_hubai(
            self._encoder_model_slug, self._encoder_model_path
        )
        self._session = self._make_session(str(path))

    def _make_session(self, path: str) -> InferenceSession:
        """NPU (QNN EP) session when running on the onnxruntime oakapp-base
        image, otherwise the original CPU session."""
        try:
            import onnxruntime_qnn  # noqa: F401  # preinstalled in the NPU base image
            from depthai_nodes.runtime import qnn_session
        except ImportError:
            self._on_npu = False
            return InferenceSession(path)
        session = qnn_session(self._pin_input_shapes(path), fp16=True)
        # shapes are pinned even if qnn_session fell back to CPU, so the
        # static-batch padding in _pad_batch must stay on either way
        self._on_npu = True
        log.info(f"{type(self).__name__}: providers={session.get_providers()}")
        return session

    def _npu_input_shape(self) -> Optional[tuple]:
        """Static shape applied to every model input on the NPU path.
        None pins each remaining dynamic dim to 1 instead."""
        return None

    def _pin_input_shapes(self, path: str) -> str:
        """The QNN EP needs static shapes; pin dynamic dims (cached on disk)."""
        import onnx
        from onnxruntime.tools.onnx_model_utils import make_dim_param_fixed

        shape = self._npu_input_shape()
        tag = "x".join(map(str, shape)) if shape else "b1"
        fixed_path = f"{os.path.splitext(path)[0]}_npu_{tag}.onnx"
        if not os.path.exists(fixed_path):
            model = onnx.load(path)
            for inp in model.graph.input:
                dims = inp.type.tensor_type.shape.dim
                for i, dim in enumerate(dims):
                    if dim.dim_value > 0 and not dim.dim_param:
                        continue  # already static
                    target = shape[i] if shape else 1
                    if dim.dim_param:
                        make_dim_param_fixed(model.graph, dim.dim_param, target)
                    else:
                        dim.dim_value = target
            onnx.save(model, fixed_path)
        return fixed_path

    #: batch sizes the NPU model gets compiled for (compiled once per bucket,
    #: cached on disk); anything larger falls back to max_num_classes
    _BATCH_BUCKETS = (8, 16, 32)

    def _pick_bucket(self, n: int) -> int:
        for bucket in self._BATCH_BUCKETS:
            if n <= bucket:
                return bucket
        return self._config.max_num_classes

    def _pad_batch(self, arr: np.ndarray) -> tuple[np.ndarray, int]:
        """Pad the batch dim to the current bucket on the NPU path (static
        shape); callers slice the output back to the original batch size."""
        n = arr.shape[0]
        target = self._batch_bucket or self._config.max_num_classes
        if not self._on_npu or n >= target:
            return arr, n
        return np.pad(arr, ((0, target - n), (0, 0)), mode="constant"), n

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
