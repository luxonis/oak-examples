import depthai as dai
from depthai_nodes.node import ParsingNeuralNetwork
from depthai.beta.node import ImgDetectionsFilter
from .nn_detection_controller import NNDetectionController
from .label_mapper_node import DetectionsLabelMapper
from prompting.encoders.textual_prompt_encoder import TextualPromptEncoder
from prompting.encoders.visual_prompt_encoder import VisualPromptEncoder


class NNDetectionNode(dai.node.ThreadedHostNode):
    """
    High-level node grouping the neural-network detection block.
    Handles object detection + filtering + annotation, and exposes a PromptController to
    update detection classes and confidence threshold at runtime.

    Internal pipeline:
        input_frame
          -> ParsingNeuralNetwork
          -> ImgDetectionsFilter (filter by enabled label IDs)
          -> LabelMapperNode (add label names for visualization)
          -> LabelMapperNode (re-add label names after bridge)

    Exposes:
      - detections_extended: ImgDetectionsExtended with label names (for visualizer)
      - detections: dai.ImgDetections with label names (for snapping)
      - controller: PromptController for dynamic prompt updates (classes, confidence threshold)
    """

    def __init__(self) -> None:
        super().__init__()

        self._nn: ParsingNeuralNetwork = self.createSubnode(ParsingNeuralNetwork)
        self._det_filter: ImgDetectionsFilter = self.createSubnode(ImgDetectionsFilter)
        self._det_filter.setRunOnHost(True)
        self._det_label_mapper_extended: DetectionsLabelMapper = self.createSubnode(
            DetectionsLabelMapper
        )
        self._det_label_mapper: DetectionsLabelMapper = self.createSubnode(
            DetectionsLabelMapper
        )

        # Internal controller
        self._controller = None

        # Prompt encoders
        self._text_encoder = None
        self._visual_encoder = None

        # Outputs
        self.detections_extended = None
        self.detections = None

    def build(
        self,
        input_frame: dai.Node.Output,
        archive,
        prompts,
        classes,
        confidence,
        iou,
    ) -> "NNDetectionNode":
        """
        @param input_frame: BGR image frames from camera.
        @param cfg: Neural network configuration.
        """
        # NN config
        self._nn.setNNArchive(archive)
        self._nn.setBackend("snpe")
        self._nn.setBackendProperties(
            {"runtime": "dsp", "performance_profile": "default"}
        )
        self._nn.setNumInferenceThreads(1)
        self._nn.getParser(0).setConfidenceThreshold(confidence)

        input_frame.link(self._nn.inputs["images"])

        # Detection filter
        self._nn.out.link(self._det_filter.input)

        # Add label for visualization (ImgDetectionsExtended)
        self._det_label_mapper_extended.build(self._det_filter.output)
        self.detections_extended = self._det_label_mapper_extended.out

        self._det_label_mapper.build(self._det_filter.output)
        self.detections = self._det_label_mapper.out

        # Prompt encoders
        self._text_encoder = TextualPromptEncoder(prompts, "yoloe", "fp16")
        self._visual_encoder = VisualPromptEncoder(prompts, "yoloe", "fp16")

        # Controller
        self._controller = NNDetectionController(
            nn=self._nn,
            text_encoder=self._text_encoder,
            visual_encoder=self._visual_encoder,
            det_filter=self._det_filter,
            det_label_mappers=[self._det_label_mapper_extended, self._det_label_mapper],
            precision="fp16",
        )
        self._controller.send_initial_prompts(
            class_names=classes,
            confidence_threshold=confidence,
        )
        self._controller.set_iou_threshold(iou)

        return self

    def run(self) -> None:
        # High-level node: no host-side processing here. Processing happens in the composed subnodes.
        pass

    def set_confidence_threshold(self, threshold: float) -> None:
        self._controller.set_confidence_threshold(threshold)

    def update_classes(self, class_names: list[str]) -> None:
        self._controller.update_classes(class_names)

    def set_iou_threshold(self, threshold: float) -> None:
        self._controller.set_iou_threshold(threshold)

    def get_state(self):
        return self._controller.get_nn_state()
