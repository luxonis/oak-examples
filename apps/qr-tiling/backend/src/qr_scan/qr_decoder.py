import depthai as dai
import numpy as np
from pyzbar.pyzbar import decode as pyzbar_decode

from depthai_nodes.node import BaseHostNode


class QRDecoder(BaseHostNode):
    """Decodes QR codes from detected bounding boxes."""

    def __init__(self) -> None:
        super().__init__()
        self._decode_enabled = True
        self._last_decoded: str = ""

    def build(
        self,
        input_frame: dai.Node.Output,
        input_detections: dai.Node.Output,
        decode_enabled: bool = True,
    ) -> "QRDecoder":
        self.link_args(input_frame, input_detections)
        self._decode_enabled = decode_enabled
        return self

    def process(self, input_frame: dai.Buffer, input_detections: dai.Buffer) -> None:
        frame = input_frame.getCvFrame()
        assert isinstance(input_detections, dai.ImgDetections)

        for det in input_detections.detections:
            det.labelName = " "
            if self._decode_enabled:
                bbox = self._denormalize_bbox(frame, det)
                decoded_text = self._decode_qr(frame, bbox)
                det.labelName = decoded_text if decoded_text else " "
        input_detections.setSequenceNum(input_frame.getSequenceNum())
        self.out.send(input_detections)

    def _decode_qr(self, frame: np.ndarray, bbox: np.ndarray) -> str:
        """Decode QR code in the given bounding box."""
        if bbox[1] >= bbox[3] or bbox[0] >= bbox[2]:
            return ""

        bbox = self._expand_bbox(bbox, frame, percentage=5)
        img = frame[bbox[1] : bbox[3], bbox[0] : bbox[2]]

        data = pyzbar_decode(img)
        if data:
            text = data[0].data.decode("utf-8")
            if text != self._last_decoded:
                self._last_decoded = text
            return text
        return ""

    def set_decode(self, value: bool) -> None:
        self._decode_enabled = value

    @property
    def decode_enabled(self) -> bool:
        return self._decode_enabled

    @staticmethod
    def _denormalize_bbox(frame: np.ndarray, det) -> np.ndarray:
        """Convert normalized detection bbox to pixel coordinates."""
        bbox = (det.xmin, det.ymin, det.xmax, det.ymax)
        norm_vals = np.full(len(bbox), frame.shape[0])
        norm_vals[::2] = frame.shape[1]
        return (np.clip(np.array(bbox), 0, 1) * norm_vals).astype(int)

    @staticmethod
    def _expand_bbox(
        bbox: np.ndarray, frame: np.ndarray, percentage: float
    ) -> np.ndarray:
        """Expand the bounding box by a percentage."""
        bbox = bbox.copy()
        h_expand = (bbox[3] - bbox[1]) * (percentage / 100)
        w_expand = (bbox[2] - bbox[0]) * (percentage / 100)
        bbox[0] = max(0, bbox[0] - w_expand)
        bbox[1] = max(0, bbox[1] - h_expand)
        bbox[2] = min(frame.shape[1], bbox[2] + w_expand)
        bbox[3] = min(frame.shape[0], bbox[3] + h_expand)
        return bbox.astype(int)
