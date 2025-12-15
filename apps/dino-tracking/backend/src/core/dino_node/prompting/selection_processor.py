import numpy as np


class SelectionProcessor:
    """
    Handles user selection in FastSAM space.

    - maps click on full-res frame -> SID
    - builds FS-space mask for the selected SID
    """

    def __init__(self):
        self._ref_mask_fs: np.ndarray | None = None

    def has_object(self) -> bool:
        return self._ref_mask_fs is not None

    def clear(self) -> None:
        self._ref_mask_fs = None

    def get_mask(self) -> np.ndarray | None:
        return self._ref_mask_fs

    def set_from_click(
        self,
        x_norm: float,
        y_norm: float,
        segmentation_full_res: np.ndarray,
        segmentation_fast_sam: np.ndarray,
    ) -> bool:
        if segmentation_full_res is None or segmentation_fast_sam is None:
            return False

        H_full, W_full = segmentation_full_res.shape

        x_full = int(x_norm * W_full)
        y_full = int(y_norm * H_full)

        x_full = max(0, min(x_full, W_full - 1))
        y_full = max(0, min(y_full, H_full - 1))

        R = 2
        x0 = max(0, x_full - R)
        x1 = min(W_full, x_full + R + 1)
        y0 = max(0, y_full - R)
        y1 = min(H_full, y_full + R + 1)

        patch = segmentation_full_res[y0:y1, x0:x1]
        if patch.size == 0:
            return False

        vals, counts = np.unique(patch, return_counts=True)
        sid = int(vals[np.argmax(counts)])

        self._ref_mask_fs = (segmentation_fast_sam == sid)

        return True
