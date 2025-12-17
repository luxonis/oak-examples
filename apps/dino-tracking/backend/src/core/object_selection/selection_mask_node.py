import numpy as np
import depthai as dai

from depthai_nodes.node import BaseHostNode
from depthai_nodes.message import SegmentationMask


class SelectionMaskNode(BaseHostNode):
    """
    A DepthAI node for handling user clicks and generating selection masks.

    This node processes user-provided clicks on a frame and generates a binary mask
    corresponding to the selected region.
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

        if self._pending_click:
            segment_id = self._map_click_to_segment(
                *self._pending_click, segmentation_fast_sam
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
        H_fs, W_fs = segmentation.shape

        x_fs = int(x_norm * W_fs)
        y_fs = int(y_norm * H_fs)

        x_fs = np.clip(x_fs, 0, W_fs - 1)
        y_fs = np.clip(y_fs, 0, H_fs - 1)

        RADIUS = 1
        x0 = max(0, x_fs - RADIUS)
        x1 = min(W_fs, x_fs + RADIUS + 1)
        y0 = max(0, y_fs - RADIUS)
        y1 = min(H_fs, y_fs + RADIUS + 1)

        patch = segmentation[y0:y1, x0:x1]
        if patch.size == 0:
            return None

        values, counts = np.unique(patch, return_counts=True)
        return int(values[np.argmax(counts)])

    def _send_mask(self, reference_frame: dai.ImgFrame, mask: np.ndarray):
        mask_u8 = mask.astype(np.uint8) * 255

        out = dai.ImgFrame()
        out.setCvFrame(mask_u8, dai.ImgFrame.Type.GRAY8)
        out.setSequenceNum(reference_frame.getSequenceNum())
        out.setTimestamp(reference_frame.getTimestamp())
        out.setTimestampDevice(reference_frame.getTimestampDevice())

        self.out.send(out)
