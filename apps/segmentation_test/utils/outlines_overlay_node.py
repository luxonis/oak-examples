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
        self.out.send(video_msg)
        return