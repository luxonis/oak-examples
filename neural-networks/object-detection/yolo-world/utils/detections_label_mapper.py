import depthai as dai
from typing import Dict


class DetectionsLabelMapper(dai.node.HostNode):
    def __init__(self, label_encoding: Dict[int, str] = {}) -> None:
        super().__init__()
        self._label_encoding = label_encoding

    def setLabelEncoding(self, label_encoding: Dict[int, str]) -> None:
        """Sets the label encoding.

        @param label_encoding: The label encoding with labels as keys and label names as
            values.
        @type label_encoding: Dict[int, str]
        """
        if not isinstance(label_encoding, Dict):
            raise ValueError("label_encoding must be a dictionary.")
        self._label_encoding = label_encoding

    def build(
        self, detections: dai.Node.Output, label_encoding: Dict[int, str] = None
    ) -> "DetectionsLabelMapper":
        if label_encoding is not None:
            self.setLabelEncoding(label_encoding)
        self.link_args(detections)
        return self

    def process(
        self,
        detections_message: dai.Buffer,
    ) -> None:
        assert isinstance(detections_message, dai.ImgDetections)
        for detection in detections_message.detections:
            detection.labelName = self._label_encoding.get(detection.label, "unknown")
        self.out.send(detections_message)
