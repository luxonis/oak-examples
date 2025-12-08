import numpy as np


class FrameCache:
    """
    Caches the last frame + segmentations.

    Used by the click processor to map FE click -> FS-space mask
    based on the previous frame's segmentation.
    """
    def __init__(self):
        self._last_frame: np.ndarray | None = None
        self._last_seg_fs: np.ndarray | None = None
        self._last_seg_full: np.ndarray | None = None

    def update(self, frame: np.ndarray, seg_fs: np.ndarray, seg_full: np.ndarray) -> None:
        self._last_frame = frame
        self._last_seg_fs = seg_fs
        self._last_seg_full = seg_full

    def get_last_seg_fs(self) -> np.ndarray | None:
        return self._last_seg_fs

    def get_last_seg_full(self) -> np.ndarray | None:
        return self._last_seg_full
