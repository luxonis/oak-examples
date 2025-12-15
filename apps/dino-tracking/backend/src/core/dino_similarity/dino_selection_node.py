import cv2
import numpy as np
import depthai as dai

from depthai_nodes.node import BaseHostNode
from .prompting.click_processor import ClickProcessor
from .similarity_engine.dino_similarity_engine import DinoSimilarityEngine


class DinoSelectionNode(BaseHostNode):
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

        self.clicks: ClickProcessor = ClickProcessor()
        self.tracker: DinoSimilarityEngine = DinoSimilarityEngine()

    def build(
        self,
        frame_in: dai.ImgFrame,
        segmentations: dai.Node.Output,
        dino_embeddings: dai.Node.Output,
        sam_size: tuple[int, int],
        dino_size: tuple[int, int],
    ):
        self.link_args(frame_in, segmentations, dino_embeddings)
        self.tracker.configure_geometry(sam_size, dino_size)
        return self

    def set_selection_click(self, x_norm: float, y_norm: float):
        self.clicks.queue_click(x_norm, y_norm)

    def clear_selection(self):
        self.clicks.clear()
        self.tracker.reset()

    def process(
        self,
        frame_msg: dai.Buffer,
        segmentation: dai.Buffer,
        dino_embedding: dai.Buffer,
    ):
        if self.clicks.process_pending_click():
            self.tracker.reset()

        H, W = self.clicks.update_cache_from_msgs(frame_msg, segmentation)
        frame_size = (H, W)

        if not self.clicks.has_object():
            heat = self.tracker.empty_heatmap(frame_size)
            self._send_heatmap(frame_msg, heat)
            return

        heat = self.tracker.process_frame(
            dino_embedding=dino_embedding,
            frame_sizes=frame_size,
            reference_segmentation=self.clicks.get_selection_mask(),
        )

        self._send_heatmap(frame_msg, heat)

    def _send_heatmap(self, reference_frame: dai.ImgFrame, heat: np.ndarray):
        heat_clipped = np.clip(heat, 0.0, 1.0)
        heat_u8 = (heat_clipped * 255.0).astype(np.uint8)
        heat_bgr = cv2.merge([heat_u8, heat_u8, heat_u8])

        out = dai.ImgFrame()
        out.setCvFrame(heat_bgr, self._img_frame_type)
        out.setSequenceNum(reference_frame.getSequenceNum())
        out.setTimestamp(reference_frame.getTimestamp())
        out.setTimestampDevice(reference_frame.getTimestampDevice())
        self.out.send(out)
