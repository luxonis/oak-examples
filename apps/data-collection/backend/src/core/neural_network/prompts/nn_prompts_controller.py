import depthai as dai
import numpy as np
from depthai_nodes.node import YOLOExtendedParser

from core.neural_network.prompts.label_manager import LabelManager
from core.neural_network.pipeline.model_state import ModelState


class NnPromptsController:
    """Handles sending conditioning inputs to the NN."""

    def __init__(
        self,
        image_prompt_queue: dai.InputQueue,
        text_prompt_queue: dai.InputQueue,
        precision: str,
        parser: YOLOExtendedParser,
        label_manager: LabelManager,
    ):
        self._image_prompt_queue = image_prompt_queue
        self._text_prompt_queue = text_prompt_queue
        self._precision = precision
        self._parser: YOLOExtendedParser = parser
        self._label_manager = label_manager

        self._model_state = ModelState()

    def _tensor_type(self) -> dai.TensorInfo.DataType:
        return (
            dai.TensorInfo.DataType.FP16
            if self._precision == "fp16"
            else dai.TensorInfo.DataType.U8F
        )

    def _send(self, queue: dai.InputQueue, name: str, data: np.ndarray):
        nn_data = dai.NNData()
        nn_data.addTensor(name, data, dataType=self._tensor_type())
        queue.send(nn_data)

    def send_prompts_pair(
        self,
        visual_prompt: np.ndarray,
        text_prompt: np.ndarray,
        class_names: list[str],
        offset: int,
    ):
        self._send(self._text_prompt_queue, "text_prompts", text_prompt)
        self._send(self._image_prompt_queue, "image_prompts", visual_prompt)
        self._label_manager.update_labels(class_names, offset)
        self._model_state.current_classes = class_names

    def set_confidence_threshold(self, threshold: float):
        self._parser.setConfidenceThreshold(threshold)
        self._model_state.confidence_threshold = threshold

    def get_model_state(self) -> ModelState:
        return self._model_state
