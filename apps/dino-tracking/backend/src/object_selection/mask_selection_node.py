import depthai as dai
import numpy as np
from depthai_nodes.message import SegmentationMask
from depthai_nodes.node import BaseHostNode


class MaskSelection(BaseHostNode):
    """
    A DepthAI node for handling user clicks and generating selection masks.

    This node processes user-provided clicks on a frame and generates a binary mask
    corresponding to the selected region.
    """

    def __init__(self):
        super().__init__()
        self._pending_click: tuple[float, float] | None = None
        self._selected_mask: np.ndarray | None = None

    def build(
        self,
        segmentations: dai.Node.Output,
    ):
        self.link_args(segmentations)
        return self

    def set_click(self, x_norm: float, y_norm: float) -> None:
        self._pending_click = (x_norm, y_norm)

    def clear_selection(self) -> None:
        self._pending_click = None
        self._selected_mask = None

    def process(self, segmentation: dai.Buffer):
        assert isinstance(segmentation, SegmentationMask)

        segmentation_mask = segmentation.mask.astype(np.int32)

        if self._pending_click:
            segment_id = self._map_click_to_segment(
                *self._pending_click, segmentation_mask
            )
            if segment_id is not None:
                self._selected_mask = segmentation_mask == segment_id
            self._pending_click = None

        if self._selected_mask is not None:
            mask_output = self._selected_mask
        else:
            segmentation_height, segmentation_width = segmentation_mask.shape
            mask_output = np.zeros(
                (segmentation_height, segmentation_width), dtype=bool
            )

        self._send_mask(segmentation, mask_output)

    def _map_click_to_segment(
        self,
        x_norm: float,
        y_norm: float,
        segmentation_mask: np.ndarray,
    ) -> int | None:
        H_segmentation, W_segmentation = segmentation_mask.shape

        x_segmentation = int(x_norm * W_segmentation)
        y_segmentation = int(y_norm * H_segmentation)

        x_segmentation = np.clip(x_segmentation, 0, W_segmentation - 1)
        y_segmentation = np.clip(y_segmentation, 0, H_segmentation - 1)

        RADIUS = 1
        x0 = max(0, x_segmentation - RADIUS)
        x1 = min(W_segmentation, x_segmentation + RADIUS + 1)
        y0 = max(0, y_segmentation - RADIUS)
        y1 = min(H_segmentation, y_segmentation + RADIUS + 1)

        patch = segmentation_mask[y0:y1, x0:x1]
        if patch.size == 0:
            return None

        values, counts = np.unique(patch, return_counts=True)
        return int(values[np.argmax(counts)])

    def _send_mask(self, segmentation: SegmentationMask, mask: np.ndarray):
        mask_u8 = mask.astype(np.uint8) * 255

        out = dai.ImgFrame()
        out.setCvFrame(mask_u8, dai.ImgFrame.Type.GRAY8)
        out.setSequenceNum(segmentation.getSequenceNum())
        out.setTimestamp(segmentation.getTimestamp())
        out.setTimestampDevice(segmentation.getTimestampDevice())

        self.out.send(out)
