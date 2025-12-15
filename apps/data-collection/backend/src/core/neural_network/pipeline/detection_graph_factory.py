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
        nn: ParsingNeuralNetwork,
    ):
        self._pipeline: dai.Pipeline = pipeline
        self._nn: ParsingNeuralNetwork = nn

    def build(self):
        det_filter = self._pipeline.create(ImgDetectionsFilter).build(self._nn.out)
        annotated_detections_as_img_det_extended = self._pipeline.create(
            AnnotationNode
        ).build(
            det_filter.out,
        )
        filtered_bridge = self._pipeline.create(ImgDetectionsBridge).build(
            det_filter.out
        )
        # this is only here until the ImgDetectionsBridge fix will be in place. now, it doesn't copy the label names
        annotated_detections_as_img_detections = self._pipeline.create(
            AnnotationNode
        ).build(
            filtered_bridge.out,
        )
        return (
            det_filter,
            annotated_detections_as_img_det_extended,
            annotated_detections_as_img_detections,
        )
