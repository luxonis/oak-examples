import depthai as dai
from config.config_data_classes import NeuralNetworkConfig
from core.neural_network.prompts.nn_prompts_controller import NnPromptsController
from core.neural_network.pipeline.annotation_node import AnnotationNode
from core.neural_network.pipeline.detection_graph_factory import DetectionGraphFactory
from core.neural_network.pipeline.nn_node_factory import NnNodeFactory
from core.neural_network.pipeline.prompt_controller_factory import (
    PromptControllerFactory,
)
from core.neural_network.pipeline.tracker_factory import TrackerFactory

from depthai_nodes.node import (
    ParsingNeuralNetwork,
    ImgDetectionsFilter,
    ImgDetectionsBridge,
)


class NNPipelineBuilder:
    """
    Facade that orchestrates the creation of all neural-network related
    DepthAI nodes and supporting controller components.
    """

    def __init__(
        self,
        pipeline: dai.Pipeline,
        video_node: dai.Node.Output,
        nn_config: NeuralNetworkConfig,
    ):
        self._pipeline: dai.Pipeline = pipeline
        self._video_node: dai.Node.Output = video_node
        self._config: NeuralNetworkConfig = nn_config

        self._nn: ParsingNeuralNetwork = None
        self._det_filter: ImgDetectionsFilter = None
        self._annotated_detections_as_img_det_extended: AnnotationNode = None
        self._annotated_detections_as_img_detections: ImgDetectionsBridge = None
        self._tracker: dai.node.ObjectTracker = None
        self._controller: NnPromptsController = None

    def build(self) -> "NNPipelineBuilder":
        """Build full neural-network subgraph."""
        nn_builder = NnNodeFactory(self._pipeline, self._video_node, self._config)
        self._nn = nn_builder.build()

        det_graph = DetectionGraphFactory(self._pipeline, self._nn)
        (
            self._det_filter,
            self._annotated_detections_as_img_det_extended,
            self._annotated_detections_as_img_detections,
        ) = det_graph.build()

        tracker_factory = TrackerFactory(
            self._pipeline,
            self._annotated_detections_as_img_detections.out,
            self._video_node,
            self._config.nn_yaml.tracker,
        )
        self._tracker = tracker_factory.build()

        controller_factory = PromptControllerFactory(
            self._nn,
            self._det_filter,
            self._annotated_detections_as_img_det_extended,
            self._annotated_detections_as_img_detections,
            self._config.model.precision,
        )
        self._controller = controller_factory.build()

    @property
    def nn(self):
        return self._nn

    @property
    def annotated_detections_as_img_det_extended(self):
        return self._annotated_detections_as_img_det_extended

    @property
    def annotated_detections_as_img_detections(self):
        return self._annotated_detections_as_img_detections

    @property
    def tracker(self):
        return self._tracker

    @property
    def controller(self):
        return self._controller
