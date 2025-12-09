import numpy as np
import depthai as dai

from .mask_to_grid_mapper import MaskToGridMapper
from .reference_embedding import ReferenceEmbedding
from .adaptive_reference_tracker import AdaptiveReferenceTracker
from .dino_feature_extractor import DinoFeatureExtractor
from .heatmap_processor import HeatmapProcessor


class DinoSimilarityEngine:
    """
    """

    def __init__(self):
        self._features = DinoFeatureExtractor()
        self._mapper = MaskToGridMapper()
        self._embed = ReferenceEmbedding()
        self._tracker = AdaptiveReferenceTracker()
        self._heatmap = HeatmapProcessor()

    def set_sizes(self, fs_size, dino_size):
        self._mapper.set_sizes(fs_size, dino_size)

    def tick_frame(self):
        self._tracker.tick()

    def reset(self):
        self._tracker.reset()
        self._heatmap.reset()

    def empty_heatmap(self, frame_shape):
        return self._heatmap.empty(frame_shape)

    def update(
        self,
        dino_msg: dai.NNData,
        frame_shape: tuple[int, int],
        reference_segmentation: np.ndarray | None,
    ) -> np.ndarray:

        grid = self._features.extract_grid(dino_msg)
        H_grid, W_grid, _ = grid.shape

        if self._tracker.reference_init is None and reference_segmentation is not None:
            is_, js = self._mapper.mask_to_grid_indices(
                reference_segmentation, (H_grid, W_grid)
            )

            if len(is_) > 0:
                vectors = grid[is_, js]
                ref = self._embed.initialize_from_vectors(vectors)
                if ref is not None:
                    self._tracker.initialize(ref)

        if not self._tracker.is_ready():
            self._heatmap.reset()
            return self._heatmap.empty(frame_shape)

        cos_grid, best_idx, best_val = self._embed.cosine_grid(
            grid,
            self._tracker.reference_init,
            self._tracker.reference_track,
            self._tracker.combine_alpha,
        )

        best_vec = self._embed.best_vector(grid, best_idx)
        self._tracker.update_tracking_reference(best_vec, best_val)

        return self._heatmap.from_cosine_grid(cos_grid, frame_shape)
