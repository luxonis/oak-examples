import cv2
import depthai as dai
import numpy as np
from depthai_nodes.message import SegmentationMask
from depthai_nodes.node.base_host_node import BaseHostNode


class OutlinesOverlay(BaseHostNode):
    """
    Takes full-res video + segmentation and draws segment outlines if active,
    else passes the video without changes
    """

    def __init__(self):
        super().__init__()
        self._is_active: bool = False
        self._kernel: np.ndarray = np.ones((3, 3), np.uint8)

    def build(self, frame: dai.ImgFrame, segmentation: dai.Node.Output):
        self.link_args(frame, segmentation)
        return self

    def set_active(self, is_active: bool):
        self._is_active = is_active

    def get_active(self) -> bool:
        return self._is_active

    def process(self, frame_msg: dai.ImgFrame, segmentation: dai.Buffer):
        if not self._is_active:
            self.out.send(frame_msg)
            return

        assert isinstance(segmentation, SegmentationMask)
        mask = getattr(segmentation, "mask", None)

        if mask is None:
            self.out.send(frame_msg)
            return

        frame = frame_msg.getCvFrame()
        H, W = frame.shape[:2]

        if mask.shape != (H, W):
            mask = cv2.resize(mask, (W, H), interpolation=cv2.INTER_NEAREST)

        mask = mask.astype(np.uint16)

        edges = cv2.morphologyEx(mask, cv2.MORPH_GRADIENT, self._kernel)

        overlay = np.zeros_like(frame)
        overlay[edges != 0] = (15, 255, 80)

        result = cv2.addWeighted(frame, 1.0, overlay, 1.0, 0.0)
        self._send(result, frame_msg)

    def _send(self, frame: np.ndarray, ref_msg: dai.ImgFrame):
        out = dai.ImgFrame()
        out.setCvFrame(frame, self._img_frame_type)
        out.setSequenceNum(ref_msg.getSequenceNum())
        out.setTimestamp(ref_msg.getTimestamp())
        out.setTimestampDevice(ref_msg.getTimestampDevice())
        self.out.send(out)
