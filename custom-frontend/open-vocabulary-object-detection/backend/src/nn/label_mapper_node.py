import logging
from typing import Dict, Optional

import depthai as dai

from depthai_nodes import ImgDetectionsExtended

logger = logging.getLogger(__name__)


class DetectionsLabelMapper(dai.node.HostNode):
    """
    Maps numeric class IDs to human-readable names.

    Input:
      - dai.ImgDetections OR ImgDetectionsExtended
    Output:
      - Same message instance, with label name fields populated.
    """

    def __init__(self, label_encoding: Optional[Dict[int, str]] = None) -> None:
        super().__init__()
        self._label_encoding = label_encoding if label_encoding is not None else {}

    def set_label_encoding(self, label_encoding: Dict[int, str]) -> None:
        """Sets the label encoding.

        @param label_encoding: The label encoding with labels as keys and label names as
            values.
        @type label_encoding: Dict[int, str]
        """
        if not isinstance(label_encoding, dict):
            raise ValueError("label_encoding must be a dictionary.")
        self._label_encoding = label_encoding

    def build(
        self,
        detections: dai.Node.Output,
        label_encoding: Optional[Dict[int, str]] = None,
    ) -> "DetectionsLabelMapper":
        if label_encoding is not None:
            self.set_label_encoding(label_encoding)

        self.link_args(detections)
        return self

    def process(self, detections_message: dai.Buffer) -> None:
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
