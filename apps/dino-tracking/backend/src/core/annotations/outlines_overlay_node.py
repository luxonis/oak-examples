import cv2
import numpy as np
import depthai as dai
from depthai_nodes.node.base_host_node import BaseHostNode


class OutlinesOverlayNode(BaseHostNode):
    """
    Takes full-res video + FastSAM segmentation and ONLY draws segment outlines.

    Modes:
      - "on":  draw outlines on top of the frame
      - "off": just forward the original frame unchanged
    """

    def __init__(self):
        super().__init__()
        self.last_seg: np.ndarray | None = None
        self.mode: str = "off"

    def build(self, video, seg):
        self.link_args(video, seg)
        return self

    def set_mode(self, mode: str):
        if mode in ("on", "off"):
            self.mode = mode
            self._logger.info(f"OutlinesOverlayNode mode set to '{mode}'")
        else:
            self._logger.warning(
                f"OutlinesOverlayNode: invalid mode '{mode}', keeping '{self.mode}'"
            )
            return {"status": "error", "message": f"Invalid mode '{mode}'"}

    def process(self, video_msg, seg_msg):
        frame = video_msg.getCvFrame()
        H, W = frame.shape[:2]

        if self.mode == "off":
            self._send(frame, video_msg)
            return

        seg = getattr(seg_msg, "mask", None)
        if seg is None:
            self._send(frame, video_msg)
            return

        if seg.shape != (H, W):
            seg = cv2.resize(seg, (W, H), interpolation=cv2.INTER_NEAREST)

        seg = seg.astype(np.int32)
        self.last_seg = seg

        overlay = np.zeros_like(frame)
        ids = np.unique(seg)
        ids = ids[ids != 0]

        for sid in ids:
            binary = np.uint8(seg == sid)
            contours, _ = cv2.findContours(
                binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )
            cv2.drawContours(overlay, contours, -1, (15, 255, 80), 1)

        result = cv2.addWeighted(frame, 1.0, overlay, 1.0, 0.0)

        self._send(result, video_msg)

    def _send(self, frame: np.ndarray, ref_msg: dai.ImgFrame):
        out = dai.ImgFrame()
        out.setCvFrame(frame, self._img_frame_type)
        out.setSequenceNum(ref_msg.getSequenceNum())
        out.setTimestamp(ref_msg.getTimestamp())
        out.setTimestampDevice(ref_msg.getTimestampDevice())
        self.out.send(out)
