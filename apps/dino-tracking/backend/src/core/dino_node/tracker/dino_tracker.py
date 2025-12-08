import numpy as np
import depthai as dai
from .dino_feature_extractor import DinoFeatureExtractor
from .reference_processor import ReferenceProcessor
from .heatmap_processor import HeatmapProcessor


class DinoTracker:
    """
        Tracking pipeline
    """

    def __init__(self):
        self._features = DinoFeatureExtractor()
        self._refs = ReferenceProcessor()
        self._heatmap = HeatmapProcessor()

    def set_sizes(self, fs_size, dino_size) -> None:
        self._refs.set_sizes(fs_size, dino_size)

    def tick_frame(self) -> None:
        self._refs.tick_frame()

    def reset(self) -> None:
        self._refs.reset()
        self._heatmap.reset()

    def empty_heatmap(self, frame_shape: tuple[int, int]) -> np.ndarray:
        return self._heatmap.empty(frame_shape)

    def update(
        self,
        dino_msg: dai.NNData,
        frame_shape: tuple[int, int],
        ref_mask_fs: np.ndarray | None,
        logger=None,
    ) -> np.ndarray:
        grid = self._features.extract_grid(dino_msg)

        initialized = self._refs.ensure_initialized(grid=grid, ref_mask_fs=ref_mask_fs, logger=logger)
        if not initialized or not self._refs.is_ready():
            self._heatmap.reset()
            return self._heatmap.empty(frame_shape)

        cos_grid = self._refs.cosine_grid_and_adapt(grid)

        return self._heatmap.from_cosine_grid(cos_grid, frame_shape)
