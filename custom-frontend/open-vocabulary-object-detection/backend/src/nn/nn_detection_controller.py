from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import depthai as dai

from depthai_nodes.node import ParsingNeuralNetwork, ImgDetectionsFilter
from .label_mapper_node import DetectionsLabelMapper
from prompting import TextualPromptEncoder
from prompting import VisualPromptEncoder


@dataclass
class NNState:
    current_classes: list[str] = field(default_factory=list)
    confidence_threshold: float = 0.0


class NNDetectionController:
    """
    Controls prompt-driven detection configuration at runtime.

    Responsibilities:
      - Produces prompt tensors (text/visual)
      - Send prompt tensors into NN input queues
      - Update label filtering + label-name encoding
      - Update parser confidence threshold
      - Track model state for FE/UI
    """

    def __init__(
        self,
        nn: ParsingNeuralNetwork,
        text_encoder: TextualPromptEncoder,
        visual_encoder: VisualPromptEncoder,
        det_filter: ImgDetectionsFilter,
        det_label_mapper: DetectionsLabelMapper,
        precision: str,
    ):
        self._nn = nn
        self._text_encoder = text_encoder
        self._visual_encoder = visual_encoder
        self._det_filter = det_filter
        self._det_label_mapper = det_label_mapper
        self._precision = precision

        self._state = NNState()

        # NN input queues
        self._text_q = self._nn.inputs["texts"].createInputQueue()
        self._img_q = self._nn.inputs["image_prompts"].createInputQueue()
        self._nn.inputs["texts"].setReusePreviousMessage(True)
        self._nn.inputs["image_prompts"].setReusePreviousMessage(True)

        self._parser = self._nn.getParser(0)

    def send_initial_prompts(
        self,
        class_names: list[str],
        detection_threshold: float,
    ) -> None:
        """Send initial prompts at startup (uses text encoder offset)."""
        self.update_classes(class_names)
        self.set_confidence_threshold(detection_threshold)

    def update_classes(self, class_names: list[str]) -> None:
        """
        Update detection classes using textual prompt embeddings.
        Uses text_encoder.offset internally.
        """
        text_embeddings = self._text_encoder.extract_embeddings(class_names)
        dummy_image = self._visual_encoder.make_dummy()

        self._apply_embedded_prompts(
            image_prompt=dummy_image,
            text_prompt=text_embeddings,
            class_names=class_names,
            label_offset=self._text_encoder.offset,
        )

    def update_visual_prompt(
        self,
        image_bgr: np.ndarray,
        class_names: list[str],
        mask: Optional[np.ndarray] = None,
    ) -> None:
        """
        Update visual prompt from an image.
        If a mask is provided, it is used to extract embeddings from the masked region.
        """
        image_embeddings = self._visual_encoder.extract_embeddings(image_bgr, mask)
        dummy_text = self._text_encoder.make_dummy()

        self._apply_embedded_prompts(
            image_prompt=image_embeddings,
            text_prompt=dummy_text,
            class_names=class_names,
            label_offset=self._visual_encoder.offset,
        )

    def set_confidence_threshold(self, threshold: float) -> None:
        t = float(max(0.0, min(1.0, threshold)))
        self._parser.setConfidenceThreshold(t)
        self._state.confidence_threshold = t

    def get_nn_state(self) -> NNState:
        return NNState(
            current_classes=list(self._state.current_classes),
            confidence_threshold=float(self._state.confidence_threshold),
        )

    def _tensor_dtype(self) -> dai.TensorInfo.DataType:
        """Get tensor data type based on model precision."""
        if self._precision == "fp16":
            return dai.TensorInfo.DataType.FP16
        return dai.TensorInfo.DataType.U8

    @staticmethod
    def _make_nn_data(
        tensor_name: str, data: np.ndarray, dtype: dai.TensorInfo.DataType
    ) -> dai.NNData:
        msg = dai.NNData()
        msg.addTensor(tensor_name, data, dataType=dtype)
        return msg

    def _update_labels(self, label_names: list[str], label_offset: int = 0) -> None:
        """Update label filtering and annotator encodings.
        @param label_names: List of class names to keep.
        @param label_offset: Label index offset (default: 0).
        """
        if label_offset < 0:
            raise ValueError("label_offset must be >= 0")

        self._det_filter.setLabels(
            labels=list(range(label_offset, label_offset + len(label_names))), keep=True
        )

        encoding = {label_offset + k: v for k, v in enumerate(label_names)}
        self._det_label_mapper.set_label_encoding(encoding)

    def _apply_embedded_prompts(
        self,
        image_prompt: np.ndarray,
        text_prompt: np.ndarray,
        class_names: list[str],
        label_offset: int = 0,
    ) -> None:
        """Send already-embedded prompts to the NN and update labels."""
        dtype = self._tensor_dtype()

        # Tensor names must match those defined in the model YAML
        self._text_q.send(self._make_nn_data("texts", text_prompt, dtype))
        self._img_q.send(self._make_nn_data("image_prompts", image_prompt, dtype))

        self._update_labels(class_names, label_offset=label_offset)
        self._state.current_classes = list(class_names)
