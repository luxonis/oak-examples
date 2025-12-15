import logging
import depthai as dai
from depthai_nodes import ImgDetectionsExtended
from typing import Dict

logger = logging.getLogger(__name__)


class AnnotationNode(dai.node.HostNode):
    def __init__(self, label_encoding: Dict[int, str] = None) -> None:
        super().__init__()
        self._label_encoding = label_encoding if label_encoding is not None else {}
        self.out_detections = self.createOutput()

    def set_label_encoding(self, label_encoding: Dict[int, str]) -> None:
        """Sets the label encoding.

        @param label_encoding: The label encoding with labels as keys and label names as
            values.
        @type label_encoding: Dict[int, str]
        """
        if not isinstance(label_encoding, Dict):
            raise ValueError("label_encoding must be a dictionary.")
        self._label_encoding = label_encoding

    def build(
        self,
        detections: dai.Node.Output,
        label_encoding: Dict[int, str] = None,
    ) -> "AnnotationNode":
        if label_encoding is not None:
            self.set_label_encoding(label_encoding)
        # Link detections and reference frame inputs
        self.link_args(detections)
        return self

    def process(
        self,
        detections_message: dai.Buffer,
    ) -> None:
        if isinstance(detections_message, ImgDetectionsExtended):
            for detection in detections_message.detections:
                detection.label_name = self._label_encoding.get(
                    detection.label, "unknown"
                )
        elif isinstance(detections_message, dai.ImgDetections):
            for detection in detections_message.detections:
                detection.labelName = self._label_encoding.get(
                    detection.label, "unknown"
                )
        self.out.send(detections_message)
