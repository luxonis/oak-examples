import cv2
import numpy as np
import depthai as dai

from depthai_nodes.node import BaseHostNode
from depthai_nodes.message import SegmentationMask


class SelectionMaskNode(BaseHostNode):
    """
    Handles user clicks and produces selection masks.
    """

    def __init__(self):
        super().__init__()
        self._pending_click: tuple[float, float] | None = None
        self._selected_mask_fs: np.ndarray | None = None

    def build(
        self,
        frame_in: dai.Node.Output,
        segmentations: dai.Node.Output,
    ):
        self.link_args(frame_in, segmentations)
        return self

    def set_click(self, x_norm: float, y_norm: float) -> None:
        self._pending_click = (x_norm, y_norm)

    def clear_selection(self) -> None:
        self._pending_click = None
        self._selected_mask_fs = None

    def process(self, frame_msg: dai.ImgFrame, segmentation: dai.Buffer):
        assert isinstance(segmentation, SegmentationMask)
        frame = frame_msg.getCvFrame()
        H_full, W_full = frame.shape[:2]

        segmentation_fast_sam = segmentation.mask.astype(np.int32)
        segmentation_full_res = cv2.resize(
            segmentation_fast_sam, (W_full, H_full), interpolation=cv2.INTER_NEAREST
        )

        if self._pending_click:
            segment_id = self._map_click_to_segment(
                *self._pending_click, segmentation_full_res
            )
            if segment_id is not None:
                self._selected_mask_fs = segmentation_fast_sam == segment_id
            self._pending_click = None

        if self._selected_mask_fs is not None:
            mask_output = self._selected_mask_fs
        else:
            H_fs, W_fs = segmentation_fast_sam.shape
            mask_output = np.zeros((H_fs, W_fs), dtype=bool)

        self._send_mask(frame_msg, mask_output)

    def _map_click_to_segment(
        self,
        x_norm: float,
        y_norm: float,
        segmentation: np.ndarray,
    ) -> int | None:
        H, W = segmentation.shape

        x_px = int(x_norm * W)
        y_px = int(y_norm * H)

        x_px = np.clip(x_px, 0, W - 1)
        y_px = np.clip(y_px, 0, H - 1)

        RADIUS = 2
        x0 = max(0, x_px - RADIUS)
        x1 = min(W, x_px + RADIUS + 1)
        y0 = max(0, y_px - RADIUS)
        y1 = min(H, y_px + RADIUS + 1)

        patch = segmentation[y0:y1, x0:x1]

        if patch.size == 0:
            return None

        values, counts = np.unique(patch, return_counts=True)
        segment_id = int(values[np.argmax(counts)])

        return segment_id

    def _send_mask(self, reference_frame: dai.ImgFrame, mask: np.ndarray):
        mask_u8 = mask.astype(np.uint8) * 255

        out = dai.ImgFrame()
        out.setCvFrame(mask_u8, dai.ImgFrame.Type.GRAY8)
        out.setSequenceNum(reference_frame.getSequenceNum())
        out.setTimestamp(reference_frame.getTimestamp())
        out.setTimestampDevice(reference_frame.getTimestampDevice())

        self.out.send(out)
