from depthai_nodes.node import ImgDetectionsFilter
from core.neural_network.pipeline.annotation_node import AnnotationNode


class LabelManager:
    """
    Manages synchronization of label data between the detection filter
    and the annotation node.

    Handles assigning numeric label IDs used by the neural network and
    mapping them to human-readable class names for visualization.
    """

    def __init__(
        self,
        det_filter: ImgDetectionsFilter,
        annotated_detections_as_img_det_extended: AnnotationNode,
        annotated_detections_as_img_detections: AnnotationNode,
    ):
        self.det_filter = det_filter
        self.annotated_detections_as_img_det_extended = (
            annotated_detections_as_img_det_extended
        )
        self.annotated_detections_as_img_detections = (
            annotated_detections_as_img_detections
        )

    def update_labels(self, label_names: list[str], offset: int = 0):
        self.det_filter.setLabels(
            labels=[i for i in range(offset, offset + len(label_names))], keep=True
        )
        self.annotated_detections_as_img_det_extended.set_label_encoding(
            {offset + k: v for k, v in enumerate(label_names)}
        )
        self.annotated_detections_as_img_detections.set_label_encoding(
            {offset + k: v for k, v in enumerate(label_names)}
        )
