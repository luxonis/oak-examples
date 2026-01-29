from typing import Optional

import depthai as dai
import numpy as np

from depthai_nodes.node import (
    ParsingNeuralNetwork,
    ImgDetectionsFilter,
)
from config import NeuralNetworkConfig
from .nn_detection_controller import NNDetectionController
from .label_mapper_node import DetectionsLabelMapper
from prompting import TextualPromptEncoder
from prompting import VisualPromptEncoder


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

    Exposes:
      - detections_extended: ImgDetectionsExtended with label names (for visualizer)
      - detections: dai.ImgDetections with label names (for snapping)
      - controller: PromptController for dynamic prompt updates (classes, confidence threshold)
    """

    def __init__(self) -> None:
        super().__init__()

        self._img_manip: dai.node.ImageManip = self.createSubnode(dai.node.ImageManip)
        self._nn: ParsingNeuralNetwork = self.createSubnode(ParsingNeuralNetwork)
        self._det_filter: ImgDetectionsFilter = self.createSubnode(ImgDetectionsFilter)
        self._det_label_mapper: DetectionsLabelMapper = self.createSubnode(DetectionsLabelMapper)

        # Internal controller
        self._controller: Optional[NNDetectionController] = None

        # Prompt encoders
        self._text_encoder: Optional[TextualPromptEncoder] = None
        self._visual_encoder: Optional[VisualPromptEncoder] = None

        # Outputs
        self.detections: Optional[dai.Node.Output] = None

    def build(
        self,
        input_frame: dai.Node.Output,
        cfg: NeuralNetworkConfig,
    ) -> "NNDetectionNode":
        """
        @param input_frame: BGR image frames from camera.
        @param cfg: Neural network configuration.
        """
        # Image manip
        self._img_manip.setMaxOutputFrameSize(cfg.model.w * cfg.model.h * 3)
        self._img_manip.initialConfig.setOutputSize(cfg.model.w, cfg.model.h)
        self._img_manip.initialConfig.setFrameType(dai.ImgFrame.Type.BGR888i)
        input_frame.link(self._img_manip.inputImage)

        # NN config
        self._nn.setNNArchive(cfg.model.archive)
        self._nn.setBackend(cfg.backend_type)
        self._nn.setBackendProperties(
            {"runtime": cfg.runtime, "performance_profile": cfg.performance_profile}
        )
        self._nn.setNumInferenceThreads(cfg.num_inference_threads)
        self._nn.getParser(0).setConfidenceThreshold(cfg.confidence_thr)
        self._img_manip.out.link(self._nn.inputs["images"])

        # Detection filter
        self._det_filter.build(self._nn.out)

        # Add label for visualization (ImgDetectionsExtended)
        self._det_label_mapper.build(self._det_filter.out)
        self.detections = self._det_label_mapper.out

        # Prompt encoders
        self._text_encoder = TextualPromptEncoder(cfg.prompts)
        self._visual_encoder = VisualPromptEncoder(cfg.prompts)

        # Controller
        self._controller = NNDetectionController(
            nn=self._nn,
            text_encoder=self._text_encoder,
            visual_encoder=self._visual_encoder,
            det_filter=self._det_filter,
            det_label_mapper=self._det_label_mapper,
            precision=cfg.model.precision,
        )
        self._controller.send_initial_prompts(
            class_names=cfg.prompts.class_names,
            detection_threshold=cfg.prompts.detection_threshold,
        )

        return self

    def run(self) -> None:
        # High-level node: no host-side processing here. Processing happens in the composed subnodes.
        pass

    def set_confidence_threshold(self, threshold: float) -> None:
        self._controller.set_confidence_threshold(threshold)

    def update_classes(self, class_names: list[str]) -> None:
        self._controller.update_classes(class_names)

    def update_visual_prompt(
        self, image: np.ndarray, class_names: list[str], mask: Optional[np.ndarray]
    ) -> None:
        self._controller.update_visual_prompt(image, class_names, mask)

    def get_state(self):
        return self._controller.get_nn_state()
