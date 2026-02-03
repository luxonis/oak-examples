from dataclasses import dataclass, field
from typing import Optional, Literal
import logging

import numpy as np
import depthai as dai

from depthai_nodes.node import ParsingNeuralNetwork, ImgDetectionsFilter
from .label_mapper_node import DetectionsLabelMapper
from prompting import TextualPromptEncoder
from prompting import VisualPromptEncoder

log = logging.getLogger(__name__)

PromptType = Literal["text", "image"]


@dataclass
class NNState:
    current_classes: list[str] = field(default_factory=list)
    image_prompt_labels: list[str] = field(default_factory=list)
    confidence_threshold: float = 0.0


class NNDetectionController:
    """
    Controls prompt-driven detection configuration at runtime.

    Supports accumulation of multiple image prompts (up to max_image_prompts),
    with rename and delete functionality.

    Responsibilities:
      - Produce and send prompt tensors (text/visual) to NN
      - Accumulate multiple image prompts with labels
      - Update label filtering and encoding
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
        model_name: str,
        precision: str,
        max_image_prompts: int = 5,
    ):
        self._nn = nn
        self._text_encoder = text_encoder
        self._visual_encoder = visual_encoder
        self._det_filter = det_filter
        self._det_label_mapper = det_label_mapper
        self._model_name = model_name.lower()
        self._precision = precision.lower()
        self._max_image_prompts = max_image_prompts

        # State
        self._state = NNState()
        self._last_text_classes: list[str] = []

        # Accumulated image prompts
        self._image_prompt_vectors: list[np.ndarray] = []
        self._image_prompt_labels: list[str] = []

        # NN input queues
        self._text_q = self._nn.inputs["texts"].createInputQueue()
        self._nn.inputs["texts"].setReusePreviousMessage(True)

        # YOLOE has separate image_prompts input; YOLO-World uses only texts
        self._img_q = None
        if self._model_name == "yoloe":
            self._img_q = self._nn.inputs["image_prompts"].createInputQueue()
            self._nn.inputs["image_prompts"].setReusePreviousMessage(True)

        self._parser = self._nn.getParser(0)

    def send_initial_prompts(
        self,
        class_names: list[str],
        confidence_threshold: float,
    ) -> None:
        """Send initial prompts at startup."""
        self.update_classes(class_names)
        self.set_confidence_threshold(confidence_threshold)

    def update_classes(self, class_names: list[str]) -> None:
        """
        Update detection classes using text prompts.
        Clears any accumulated image prompts and switches to text-based detection.
        """
        max_n = self._text_encoder.max_num_classes
        if len(class_names) > max_n:
            log.warning(f"Too many classes ({len(class_names)} > {max_n}); truncating.")
            class_names = class_names[:max_n]

        self._last_text_classes = list(class_names)

        text_embeddings = self._text_encoder.extract_embeddings(class_names)
        dummy_image = self._visual_encoder.make_dummy()

        self._apply_embedded_prompts(
            image_prompt=dummy_image,
            text_prompt=text_embeddings,
            class_names=class_names,
            label_offset=self._text_encoder.offset,
            prompt_type="text",
        )

        # Clear accumulated image prompts
        self._image_prompt_vectors = []
        self._image_prompt_labels = []
        self._state.image_prompt_labels = []

        log.info(f"Text classes updated: {class_names}")

    def add_image_prompt(
        self,
        image_bgr: np.ndarray,
        label: str,
        mask: Optional[np.ndarray] = None,
    ) -> None:
        """
        Add an image prompt to the accumulated list.
        Extracts visual embeddings and adds to the list. If at max capacity,
        removes the oldest prompt.

        @param image_bgr: BGR image to extract embeddings from.
        @param label: Label for this prompt.
        @param mask: Optional mask for region-based extraction.
        """
        embeddings = self._visual_encoder.extract_embeddings(image_bgr, mask)
        embeddings_vector = embeddings[0, :, 0].copy()

        self._image_prompt_vectors.append(embeddings_vector)
        self._image_prompt_labels.append(label)

        if len(self._image_prompt_vectors) > self._max_image_prompts:
            removed = self._image_prompt_labels[0]
            self._image_prompt_vectors = self._image_prompt_vectors[
                -self._max_image_prompts :
            ]
            self._image_prompt_labels = self._image_prompt_labels[
                -self._max_image_prompts :
            ]
            log.info(f"Max prompts reached, removed oldest: '{removed}'")

        self._send_accumulated_image_prompts()

        log.info(
            f"Added image prompt '{label}' (total: {len(self._image_prompt_labels)})"
        )

    def add_bbox_prompt(
        self,
        image_bgr: np.ndarray,
        label: str,
        x0: int,
        y0: int,
        x1: int,
        y1: int,
    ) -> None:
        if self._model_name == "yolo-world":
            crop = image_bgr[y0:y1, x0:x1]
            self.add_image_prompt(crop, label, mask=None)
        else:
            H, W = image_bgr.shape[:2]
            mask = np.zeros((H, W), dtype=np.float32)
            mask[y0:y1, x0:x1] = 1.0
            self.add_image_prompt(image_bgr, label, mask=mask)

    def rename_image_prompt(
        self, index: int = None, old_label: str = None, new_label: str = None
    ) -> bool:
        """
        Rename an image prompt by index or old label.

        @param index: Index of the prompt to rename.
        @param old_label: Current label.
        @param new_label: New label to assign.
        """
        if not new_label:
            log.warning("rename_image_prompt: new_label is required")
            return False

        idx = None
        if isinstance(index, int) and 0 <= index < len(self._image_prompt_labels):
            idx = index
        elif old_label and old_label in self._image_prompt_labels:
            idx = self._image_prompt_labels.index(old_label)

        if idx is None:
            log.warning("rename_image_prompt: index/old_label not found")
            return False

        old = self._image_prompt_labels[idx]
        self._image_prompt_labels[idx] = new_label
        self._state.image_prompt_labels = list(self._image_prompt_labels)

        self._update_labels(
            self._image_prompt_labels,
            label_offset=self._visual_encoder.offset,
        )

        log.info(f"Renamed image prompt '{old}' -> '{new_label}'")
        return True

    def delete_image_prompt(self, index: int = None, label: str = None) -> bool:
        """
        Delete an image prompt by index or label.
        If all image prompts are deleted, reverts to last text classes.

        @param index: Index of the prompt to delete.
        @param label: Current label.
        """
        idx = None
        if isinstance(index, int) and 0 <= index < len(self._image_prompt_vectors):
            idx = index
        elif label and label in self._image_prompt_labels:
            idx = self._image_prompt_labels.index(label)

        if idx is None:
            log.warning("delete_image_prompt: index/label not found")
            return False

        removed_label = self._image_prompt_labels[idx]
        del self._image_prompt_vectors[idx]
        del self._image_prompt_labels[idx]

        if len(self._image_prompt_vectors) > 0:
            self._send_accumulated_image_prompts()
            log.info(
                f"Deleted image prompt '{removed_label}' (remaining: {len(self._image_prompt_labels)})"
            )
        else:
            self._revert_to_text_classes()
            log.info(
                f"Deleted last image prompt '{removed_label}', reverted to text classes"
            )

        return True

    def set_confidence_threshold(self, threshold: float) -> None:
        """Set the confidence threshold for detection."""
        t = float(max(0.0, min(1.0, threshold)))
        self._parser.setConfidenceThreshold(t)
        self._state.confidence_threshold = t
        log.info(f"Confidence threshold set to {t:.2f}")

    def get_nn_state(self) -> NNState:
        """Get current NN state for frontend synchronization."""
        return NNState(
            current_classes=list(self._state.current_classes),
            image_prompt_labels=list(self._state.image_prompt_labels),
            confidence_threshold=float(self._state.confidence_threshold),
        )

    def _send_accumulated_image_prompts(self) -> None:
        """Build combined tensor from accumulated vectors and send to NN."""
        combined = self._visual_encoder.make_dummy()
        for i, vec in enumerate(self._image_prompt_vectors):
            combined[0, :, i] = vec
        dummy_text = self._text_encoder.make_dummy()

        self._apply_embedded_prompts(
            image_prompt=combined,
            text_prompt=dummy_text,
            class_names=self._image_prompt_labels,
            label_offset=self._visual_encoder.offset,
            prompt_type="image",
        )

        self._state.image_prompt_labels = list(self._image_prompt_labels)

    def _revert_to_text_classes(self) -> None:
        """Revert to last text classes when all image prompts are deleted."""
        if not self._last_text_classes:
            self._last_text_classes = ["object"]

        text_embeddings = self._text_encoder.extract_embeddings(self._last_text_classes)
        dummy_image = self._visual_encoder.make_dummy()

        self._apply_embedded_prompts(
            image_prompt=dummy_image,
            text_prompt=text_embeddings,
            class_names=self._last_text_classes,
            label_offset=self._text_encoder.offset,
            prompt_type="text",
        )

        self._state.image_prompt_labels = []
        log.info(f"Reverted to text classes: {self._last_text_classes}")

    def _tensor_dtype(self) -> dai.TensorInfo.DataType:
        """Get tensor data type based on model precision."""
        if self._precision == "fp16":
            return dai.TensorInfo.DataType.FP16
        return dai.TensorInfo.DataType.U8F

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
            labels=list(range(label_offset, label_offset + len(label_names))),
            keep=True,
        )

        encoding = {label_offset + k: v for k, v in enumerate(label_names)}
        self._det_label_mapper.set_label_encoding(encoding)

    def _apply_embedded_prompts(
        self,
        image_prompt: np.ndarray,
        text_prompt: np.ndarray,
        class_names: list[str],
        label_offset: int = 0,
        prompt_type: PromptType = "text",
    ) -> None:
        """Send embedded prompts to the NN and update labels.

        @param image_prompt: Image prompt embeddings tensor.
        @param text_prompt: Text prompt embeddings tensor.
        @param class_names: List of class names for labels.
        @param label_offset: Label index offset.
        @param prompt_type: "text" or "image" - which prompt is active.
        """
        dtype = self._tensor_dtype()

        if self._model_name == "yolo-world":
            # YOLO-World: single texts input, send whichever prompt is active
            if prompt_type == "text":
                self._text_q.send(self._make_nn_data("texts", text_prompt, dtype))
            else:
                self._text_q.send(self._make_nn_data("texts", image_prompt, dtype))
        else:
            # YOLOE: separate texts and image_prompts inputs
            self._text_q.send(self._make_nn_data("texts", text_prompt, dtype))
            self._img_q.send(self._make_nn_data("image_prompts", image_prompt, dtype))

        self._update_labels(class_names, label_offset=label_offset)
        self._state.current_classes = list(class_names)
