import numpy as np


class MaskToGridMapper:
    """
    Converts a SAM resolution mask into DINO feature grid coordinates
    """

    def __init__(self):
        self.sam_w: int = None
        self.sam_h: int = None
        self.dino_w: int = None
        self.dino_h: int = None

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

    def segmentation_to_grid_indices(
        self, segmentation: np.ndarray, grid_shape: tuple[int, int]
    ) -> tuple[np.ndarray, np.ndarray]:
        if not self.is_ready():
            return np.array([]), np.array([])

        grid_h, grid_w = grid_shape

        # Find all selected pixels
        y_segmentation, x_segmentation = np.where(segmentation)
        if len(x_segmentation) == 0:
            return np.array([]), np.array([])

        # FS → DINO input coordinate system
        x_dino = (x_segmentation.astype(np.float32) / float(self.sam_w)) * float(
            self.dino_w
        )
        y_dino = (y_segmentation.astype(np.float32) / float(self.sam_h)) * float(
            self.dino_h
        )

        x_dino = np.clip(x_dino, 0, self.dino_w - 1)
        y_dino = np.clip(y_dino, 0, self.dino_h - 1)

        # DINO input → DINO grid coordinates
        grid_x = (x_dino / float(self.dino_w) * float(grid_w)).astype(np.int32)
        grid_y = (y_dino / float(self.dino_h) * float(grid_h)).astype(np.int32)

        grid_x = np.clip(grid_x, 0, grid_w - 1)
        grid_y = np.clip(grid_y, 0, grid_h - 1)

        return grid_y, grid_x
