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
        input_node: dai.Node.Output,
        nn_config: NeuralNetworkConfig,
    ):
        self._pipeline: dai.Pipeline = pipeline
        self._input_node: dai.Node.Output = input_node
        self._config: NeuralNetworkConfig = nn_config

        self._nn: ParsingNeuralNetwork = None
        self._det_filter: ImgDetectionsFilter = None
        self._annotation_node: AnnotationNode = None
        self._filtered_bridge: ImgDetectionsBridge = None
        self._tracker: dai.node.ObjectTracker = None
        self._controller: NnPromptsController = None

    def build(self) -> "NNPipelineBuilder":
        """Build full neural-network subgraph."""
        nn_builder = NnNodeFactory(self._pipeline, self._input_node, self._config)
        self._nn = nn_builder.build()

        det_graph = DetectionGraphFactory(self._pipeline, self._input_node, self._nn)
        self._det_filter, self._annotation_node, self._filtered_bridge = (
            det_graph.build()
        )

        tracker_factory = TrackerFactory(
            self._pipeline,
            self._filtered_bridge.out,
            self._input_node,
            self._config.nn_yaml.tracker,
        )
        self._tracker = tracker_factory.build()

        controller_factory = PromptControllerFactory(
            self._nn,
            self._det_filter,
            self._annotation_node,
            self._config.model.precision,
        )
        self._controller = controller_factory.build()

    @property
    def nn(self):
        return self._nn

    @property
    def detections(self):
        return self._filtered_bridge

    @property
    def tracker(self):
        return self._tracker

    @property
    def annotation_node(self):
        return self._annotation_node

    @property
    def controller(self):
        return self._controller
