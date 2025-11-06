import depthai as dai
from depthai_nodes.node import (
    ParsingNeuralNetwork,
    ImgDetectionsFilter,
    ImgDetectionsBridge,
)
from config.config_data_classes import NeuralNetworkConfig
from core.label_manager import LabelManager
from core.infrastructure.neural_network.annotation_node import AnnotationNode
from core.controllers.nn_prompts_controller import NnPromptsController
from core.model_state import ModelState


class NNPipelineSetup:
    """
    Handles creation of all neural network–related nodes in a DepthAI pipeline.
    """

    def __init__(
        self,
        pipeline: dai.Pipeline,
        input_node: dai.Node.Output,
        nn_config: NeuralNetworkConfig,
        model_state: ModelState,
    ):
        self._pipeline = pipeline
        self._input_node = input_node
        self._nn_config = nn_config
        self._model_state = model_state

        self._nn = None
        self._prompt_controller = None
        self._det_filter = None
        self._annotation_node = None
        self._filtered_bridge = None
        self._tracker = None

    def build(self) -> "NNPipelineSetup":
        self._build_nn()
        self._build_filters()
        self._build_tracker()
        self._build_controller()
        return self

    def _build_nn(self):
        backend = self._nn_config.nn_yaml.nn_backend

        nn = self._pipeline.create(ParsingNeuralNetwork)
        nn.setNNArchive(self._nn_config.model.archive)
        nn.setBackend(backend.type)
        nn.setBackendProperties(
            {
                "runtime": backend.runtime,
                "performance_profile": backend.performance_profile,
            }
        )
        nn.setNumInferenceThreads(backend.inference_threads)
        nn.getParser(0).setConfidenceThreshold(backend.confidence_threshold)

        self._input_node.link(nn.inputs["images"])
        self._nn = nn

    def _build_filters(self):
        if not self._nn:
            raise RuntimeError("Neural Network must be built before filters.")

        det_filter = self._pipeline.create(ImgDetectionsFilter).build(self._nn.out)
        annotation_node = self._pipeline.create(AnnotationNode).build(
            det_filter.out, self._input_node
        )
        filtered_bridge = self._pipeline.create(ImgDetectionsBridge).build(
            det_filter.out
        )

        self._det_filter = det_filter
        self._annotation_node = annotation_node
        self._filtered_bridge = filtered_bridge

    def _build_tracker(self):
        if not self._filtered_bridge:
            raise RuntimeError("Detections must be built before tracker.")

        tcfg = self._nn_config.nn_yaml.tracker
        tracker = self._pipeline.create(dai.node.ObjectTracker)

        tracker.setTrackerType(dai.TrackerType.SHORT_TERM_IMAGELESS)
        tracker.setTrackerIdAssignmentPolicy(dai.TrackerIdAssignmentPolicy.UNIQUE_ID)
        tracker.setTrackingPerClass(tcfg.track_per_class)
        tracker.setTrackletBirthThreshold(tcfg.birth_threshold)
        tracker.setTrackletMaxLifespan(tcfg.max_lifespan)
        tracker.setOcclusionRatioThreshold(tcfg.occlusion_ratio_threshold)
        tracker.setTrackerThreshold(tcfg.tracker_threshold)

        source = self._input_node
        source.link(tracker.inputTrackerFrame)
        source.link(tracker.inputDetectionFrame)
        self._filtered_bridge.out.link(tracker.inputDetections)

        self._tracker = tracker

    def _build_controller(self):
        if not self._nn:
            raise RuntimeError("Neural Network must be built before controller.")

        text_q = self._nn.inputs["texts"].createInputQueue()
        img_q = self._nn.inputs["image_prompts"].createInputQueue()
        self._nn.inputs["texts"].setReusePreviousMessage(True)
        self._nn.inputs["image_prompts"].setReusePreviousMessage(True)

        parser = self._nn.getParser(0)
        label_manager = LabelManager(self._det_filter, self._annotation_node)
        self._prompt_controller = NnPromptsController(
            img_q,
            text_q,
            self._nn_config.model.precision,
            parser,
            self._model_state,
            label_manager,
        )

    @property
    def nn(self) -> ParsingNeuralNetwork:
        return self._nn

    @property
    def controller(self) -> NnPromptsController:
        return self._prompt_controller

    @property
    def detections(self) -> ImgDetectionsBridge:
        return self._filtered_bridge

    @property
    def tracker(self) -> dai.node.ObjectTracker:
        return self._tracker

    @property
    def annotation_node(self) -> AnnotationNode:
        return self._annotation_node
