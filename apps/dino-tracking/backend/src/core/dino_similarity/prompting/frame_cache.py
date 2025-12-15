import numpy as np


class FrameCache:
    """
    Caches the last frame + segmentations.

    Used by the click processor to map FE click -> FS-space mask
    based on the previous frame's segmentation.
    """

    def __init__(self):
        self._last_frame: np.ndarray | None = None
        self._last_seg_fast_sam: np.ndarray | None = None
        self._last_seg_full_res: np.ndarray | None = None

    def update(
        self,
        frame: np.ndarray,
        segmentation_fast_sam: np.ndarray,
        segmentation_full_res: np.ndarray,
    ) -> None:
        self._last_frame = frame
        self._last_seg_fast_sam = segmentation_fast_sam
        self._last_seg_full_res = segmentation_full_res

    def get_last_seg_fs(self) -> np.ndarray | None:
        return self._last_seg_fast_sam

    def get_last_seg_full(self) -> np.ndarray | None:
        return self._last_seg_full_res
