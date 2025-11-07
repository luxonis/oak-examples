from core.neural_network.pipeline.annotation_node import AnnotationNode
from core.neural_network.prompts.nn_prompts_controller import NnPromptsController
from core.label_manager import LabelManager
from depthai_nodes.node import ParsingNeuralNetwork, ImgDetectionsFilter


class PromptControllerFactory:
    """Creates and configures the NnPromptsController and LabelManager."""

    def __init__(
        self,
        nn_node: ParsingNeuralNetwork,
        det_filter: ImgDetectionsFilter,
        annotation_node: AnnotationNode,
        precision: str,
    ):
        self._nn_node: ParsingNeuralNetwork = nn_node
        self._det_filter: ImgDetectionsFilter = det_filter
        self._annotation_node: AnnotationNode = annotation_node
        self._precision: str = precision

    def build(self) -> NnPromptsController:
        text_q = self._nn_node.inputs["texts"].createInputQueue()
        img_q = self._nn_node.inputs["image_prompts"].createInputQueue()
        self._nn_node.inputs["texts"].setReusePreviousMessage(True)
        self._nn_node.inputs["image_prompts"].setReusePreviousMessage(True)

        parser = self._nn_node.getParser(0)
        label_manager = LabelManager(self._det_filter, self._annotation_node)

        controller = NnPromptsController(
            img_q, text_q, self._precision, parser, label_manager
        )

        return controller
