import logging
from typing import Dict, Optional

import depthai as dai

from depthai_nodes import ImgDetectionsExtended

logger = logging.getLogger(__name__)


class DetectionsLabelMapper(dai.node.HostNode):
    """
    Adds label names to detections and aligns detections to a reference frame.

    Inputs:
      - input_detections: dai.ImgDetections or ImgDetectionsExtended
      - input_frame: dai.ImgFrame (reference coordinate space)

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
        input_detections: dai.Node.Output,
        input_frame: dai.Node.Output,
        label_encoding: Optional[Dict[int, str]] = None,
    ) -> "DetectionsLabelMapper":
        if label_encoding is not None:
            self.set_label_encoding(label_encoding)

        self.link_args(input_detections, input_frame)
        return self

    def process(
        self, detections_message: dai.Buffer, frame_message: dai.ImgFrame
    ) -> None:
        if isinstance(detections_message, ImgDetectionsExtended):
            # Align detections to frame coordinate space
            detections_message.setTransformation(frame_message.getTransformation())
            for detection in detections_message.detections:
                detection.label_name = self._label_encoding.get(
                    detection.label, "unknown"
                )
        elif isinstance(detections_message, dai.ImgDetections):
            detections_message.setTransformation(frame_message.getTransformation())
            for detection in detections_message.detections:
                detection.labelName = self._label_encoding.get(
                    detection.label, "unknown"
                )
        self.out.send(detections_message)
