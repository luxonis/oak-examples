from typing import Optional

import depthai as dai
import numpy as np
from depthai_nodes.node import BaseHostNode

from dino_similarity.dino_grid_extractor_node import DinoGrid


class InitVectors(dai.Buffer):
    """
    A custom DepthAI buffer to hold initialized vectors extracted from the DINO grid.

    Attributes
    ----------
    vectors : Optional[np.ndarray]
        The extracted vectors, represented as a NumPy array. Defaults to None.
    """

    vectors: Optional[np.ndarray] = None


class ReferenceVectorFromSelection(BaseHostNode):
    """
    A DepthAI node that extracts DINO features from regions specified by a mask.

    Processes a selection mask and DINO grid to send extracted vectors as `InitVectors`.
    """

    def __init__(self):
        super().__init__()
        self._last_mask: np.ndarray | None = None
        self._dino_input_size: tuple[int, int] | None = None
        self._last_vectors = None

    def build(
        self,
        mask_in: dai.Node.Output,
        dino_in: dai.Node.Output,
        dino_input_size: tuple[int, int],
    ):
        self._dino_input_size = dino_input_size
        self.link_args(mask_in, dino_in)
        return self

    def process(self, mask_msg: dai.Buffer, dino_grid: dai.Buffer):
        assert isinstance(mask_msg, dai.ImgFrame)
        assert isinstance(dino_grid, DinoGrid)
        mask = mask_msg.getCvFrame() > 0

        if self._mask_changed(mask):
            self._last_mask = mask.copy() if mask.any() else None

            if mask.any():
                self._last_vectors = self._extract_vectors(mask, dino_grid.grid)
            else:
                self._last_vectors = None

        out = InitVectors()
        out.vectors = self._last_vectors

        out.setSequenceNum(mask_msg.getSequenceNum())
        out.setTimestamp(mask_msg.getTimestamp())
        out.setTimestampDevice(mask_msg.getTimestampDevice())

        self.out.send(out)

    def _extract_vectors(self, mask: np.ndarray, dino_grid: np.ndarray) -> np.ndarray:
        H_grid, W_grid, D = dino_grid.shape
        H_mask, W_mask = mask.shape

        y_mask, x_mask = np.where(mask)
        if len(x_mask) == 0:
            return np.empty((0, D), dtype=np.float32)

        x_grid = (x_mask / W_mask * W_grid).astype(np.int32)
        y_grid = (y_mask / H_mask * H_grid).astype(np.int32)

        x_grid = np.clip(x_grid, 0, W_grid - 1)
        y_grid = np.clip(y_grid, 0, H_grid - 1)

        return dino_grid[y_grid, x_grid]

    def _mask_changed(self, mask: np.ndarray) -> bool:
        if self._last_mask is None:
            return mask.any()
        if not mask.any():
            return True
        return not np.array_equal(mask, self._last_mask)
