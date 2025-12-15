import numpy as np
import depthai as dai

from core.dino_similarity.similarity_engine.features.dino_feature_extractor import DinoFeatureExtractor
from core.dino_similarity.similarity_engine.features.mask_to_grid_mapper import MaskToGridMapper


class DinoFeatureSpace:
    """
    Owns the DINO feature grid for the current frame and all
    coordinate / mask mapping logic.
    """

    def __init__(self):
        self._extractor = DinoFeatureExtractor()
        self._mapper = MaskToGridMapper()
        self._grid: np.ndarray | None = None

    def set_sizes(self, fast_sam_size, dino_size):
        self._mapper.set_sizes(fast_sam_size, dino_size)

    def begin_frame(self, dino_embeddings: dai.NNData) -> None:
        self._grid = self._extractor.extract_grid(dino_embeddings)

    def _require_grid(self) -> np.ndarray:
        if self._grid is None:
            raise RuntimeError("DinoFeatureSpace: grid not initialized for frame")
        return self._grid

    def reference_vectors_from_segmentation(
        self,
        segmentation: np.ndarray,
    ) -> np.ndarray:
        grid = self._require_grid()

        H, W, _ = grid.shape
        is_, js = self._mapper.segmentation_to_grid_indices(segmentation, (H, W))

        if len(is_) == 0:
            return np.empty((0, grid.shape[-1]), dtype=np.float32)

        return grid[is_, js]

    def get_grid(self) -> np.ndarray:
        return self._require_grid()
