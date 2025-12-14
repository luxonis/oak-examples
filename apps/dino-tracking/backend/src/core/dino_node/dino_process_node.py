import cv2
import numpy as np
import depthai as dai

from depthai_nodes.node import BaseHostNode
from .prompting.click_processor import ClickProcessor
from .tracker.dino_similarity_engine import DinoSimilarityEngine


class DinoProcessNode(BaseHostNode):
    """
    Per frame:
      - process pending click (using cached previous frame)
      - if nothing is selected -> output zero heatmap
      - otherwise:
          * run DINO tracker (two refs: init + track)
          * cos = combine_alpha * cos_track + (1 - combine_alpha) * cos_init
      - output heatmap (0..255)
    """

    def __init__(self):
        super().__init__()

        self.clicks = ClickProcessor()
        self.tracker = DinoSimilarityEngine()

    def build(self, frame_in: dai.ImgFrame, seg_in: dai.Node.Output, dino_in: dai.Node.Output, sam_size: dai.Node.Output, dino_size: tuple[int, int]):
        self.link_args(frame_in, seg_in, dino_in)
        self.tracker.set_sizes(sam_size, dino_size)
        return self

    def set_selection_click(self, x_norm: float, y_norm: float):
        self.clicks.queue_click(x_norm, y_norm)

    def clear_selection(self):
        self.clicks.clear()
        self.tracker.reset()

    def process(self, frame_msg: dai.Buffer, seg_msg: dai.Buffer, dino_msg: dai.Buffer):
        selection_changed = self.clicks.process_pending_click()

        if selection_changed:
            self.tracker.reset()

        self.tracker.tick_frame()

        H_full, W_full = self.clicks.update_cache_from_msgs(frame_msg, seg_msg)
        frame_shape = (H_full, W_full)

        if not self.clicks.has_object():
            heat = self.tracker.empty_heatmap(frame_shape)
            self._send_heatmap(frame_msg, heat)
            return

        reference_segmentation = self.clicks.get_selection_mask()

        heat = self.tracker.update(
            dino_msg=dino_msg,
            frame_shape=frame_shape,
            reference_segmentation=reference_segmentation,
        )

        self._send_heatmap(frame_msg, heat)

    def _send_heatmap(self, ref_msg: dai.ImgFrame, heat: np.ndarray):
        heat_clipped = np.clip(heat, 0.0, 1.0)
        heat_u8 = (heat_clipped * 255.0).astype(np.uint8)
        heat_bgr = cv2.merge([heat_u8, heat_u8, heat_u8])

        out = dai.ImgFrame()
        out.setCvFrame(heat_bgr, self._img_frame_type)
        out.setSequenceNum(ref_msg.getSequenceNum())
        out.setTimestamp(ref_msg.getTimestamp())
        out.setTimestampDevice(ref_msg.getTimestampDevice())
        self.out.send(out)
