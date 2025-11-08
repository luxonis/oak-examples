import depthai as dai
from depthai_nodes.node import ImgDetectionsFilter, ImgDetectionsBridge
from core.neural_network.pipeline.annotation_node import AnnotationNode
from depthai_nodes.node import ParsingNeuralNetwork


class DetectionGraphFactory:
    """
    Builds the detection-processing subgraph:
      ParsingNeuralNetwork → ImgDetectionsFilter ─┬─→ AnnotationNode
                                             └─→ ImgDetectionsBridge
    """

    def __init__(
        self,
        pipeline: dai.Pipeline,
        video_node: dai.Node.Output,
        nn: ParsingNeuralNetwork,
    ):
        self._pipeline: dai.Pipeline = pipeline
        self._video_node: dai.Node.Output = video_node
        self._nn: ParsingNeuralNetwork = nn

    def build(self):
        det_filter = self._pipeline.create(ImgDetectionsFilter).build(self._nn.out)
        annotation_node = self._pipeline.create(AnnotationNode).build(
            det_filter.out, self._video_node
        )
        filtered_bridge = self._pipeline.create(ImgDetectionsBridge).build(
            det_filter.out
        )
        return det_filter, annotation_node, filtered_bridge
