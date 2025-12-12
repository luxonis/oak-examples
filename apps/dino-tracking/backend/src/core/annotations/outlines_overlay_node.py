import cv2
import numpy as np
import depthai as dai
from depthai_nodes.node.base_host_node import BaseHostNode


class OutlinesOverlayNode(BaseHostNode):
    """
    Takes full-res video + FastSAM segmentation and draws segment outlines if active,
    else passes the video without changes
    """

    def __init__(self):
        super().__init__()
        self.last_seg: np.ndarray | None = None
        self._is_active: bool = False
        self.kernel = np.ones((3, 3), np.uint8)

    def build(self, video, seg):
        self.link_args(video, seg)
        return self

    def set_active(self, is_active: bool):
        self._is_active = is_active

    def get_active(self) -> bool:
        return self._is_active

    def process(self, video_msg, seg_msg):
        frame = video_msg.getCvFrame()
        H, W = frame.shape[:2]

        if not self._is_active:
            self._send(frame, video_msg)
            return

        seg = getattr(seg_msg, "mask", None)
        if seg is None:
            self._send(frame, video_msg)
            return

        if seg.shape != (H, W):
            seg = cv2.resize(seg, (W, H), interpolation=cv2.INTER_NEAREST)

        seg = seg.astype(np.uint16)
        self.last_seg = seg

        edges = cv2.morphologyEx(seg, cv2.MORPH_GRADIENT, self.kernel)

        overlay = np.zeros_like(frame)
        overlay[edges != 0] = (15, 255, 80)

        result = cv2.addWeighted(frame, 1.0, overlay, 1.0, 0.0)
        self._send(result, video_msg)

    def _send(self, frame: np.ndarray, ref_msg: dai.ImgFrame):
        out = dai.ImgFrame()
        out.setCvFrame(frame, self._img_frame_type)
        out.setSequenceNum(ref_msg.getSequenceNum())
        out.setTimestamp(ref_msg.getTimestamp())
        out.setTimestampDevice(ref_msg.getTimestampDevice())
        self.out.send(out)
