import numpy as np
import depthai as dai

from depthai_nodes.node import BaseHostNode

from core.dino_similarity.vector_manager import VectorManager


class ReferenceVectorNode(BaseHostNode):
    """
    Extracts DINO features from selected regions and initializes reference.

    Input: selection_mask, dino_embeddings
    Output: sync message (triggers downstream processing)
    """

    def __init__(self):
        super().__init__()
        self._manager: VectorManager | None = None
        self._last_mask: np.ndarray | None = None

        # Feature extraction
        self._dino_input_size: tuple[int, int] | None = None
        self._sam_size: tuple[int, int] | None = None

    def build(
        self,
        manager: VectorManager,
        mask_in: dai.Node.Output,
        dino_in: dai.Node.Output,
        dino_input_size: tuple[int, int],
    ):
        self._manager = manager
        self._dino_input_size = dino_input_size
        self.link_args(mask_in, dino_in)
        return self

    def process(self, mask_msg: dai.Buffer, dino_grid: dai.Buffer):
        mask = mask_msg.getCvFrame() > 0

        if self._mask_changed(mask):
            self._manager.reset()
            self._last_mask = mask.copy() if mask.any() else None

            if mask.any():
                vectors = self._extract_vectors(mask, dino_grid.grid)
                self._manager.initialize(vectors)

        self.out.send(dino_grid)

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
