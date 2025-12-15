import numpy as np


class MaskToGridMapper:
    """
    Converts a SAM resolution mask into DINO feature grid coordinates
    """

    def __init__(self):
        self.sam_w = None
        self.sam_h = None
        self.dino_w = None
        self.dino_h = None

    def set_sizes(self, fs_size: tuple[int, int], dino_size: tuple[int, int]) -> None:
        self.sam_w, self.sam_h = fs_size
        self.dino_w, self.dino_h = dino_size

    def is_ready(self) -> bool:
        return (
            self.sam_w is not None
            and self.sam_h is not None
            and self.dino_w is not None
            and self.dino_h is not None
        )

    def mask_to_grid_indices(self, ref_mask_fs: np.ndarray, grid_shape: tuple[int, int]) -> tuple[np.ndarray, np.ndarray]:

        if not self.is_ready():
            return np.array([]), np.array([])

        H_grid, W_grid = grid_shape

        # Find all selected pixels
        ys, xs = np.where(ref_mask_fs)
        if len(xs) == 0:
            return np.array([]), np.array([])

        # FS → DINO input coordinate system
        xs_d = (xs.astype(np.float32) / float(self.sam_w)) * float(self.dino_w)
        ys_d = (ys.astype(np.float32) / float(self.sam_h)) * float(self.dino_h)

        xs_d = np.clip(xs_d, 0, self.dino_w - 1)
        ys_d = np.clip(ys_d, 0, self.dino_h - 1)

        # DINO input → DINO grid coordinates
        js = (xs_d / float(self.dino_w) * float(W_grid)).astype(np.int32)
        is_ = (ys_d / float(self.dino_h) * float(H_grid)).astype(np.int32)

        js = np.clip(js, 0, W_grid - 1)
        is_ = np.clip(is_, 0, H_grid - 1)

        return is_, js
