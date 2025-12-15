import numpy as np
import depthai as dai

from core.dino_similarity.similarity_engine.features.dino_feature_space import (
    DinoFeatureSpace,
)
from core.dino_similarity.similarity_engine.heatmap_producer import HeatmapProducer
from core.dino_similarity.similarity_engine.references.reference_system import (
    ReferenceSystem,
)


class DinoSimilarityEngine:
    """
    Stateful per-stream DINO similarity tracker.
    """

    def __init__(self):
        self._features = DinoFeatureSpace()
        self._reference = ReferenceSystem()
        self._heatmap = HeatmapProducer()

    def configure_geometry(self, fs_size, dino_size):
        self._features.set_sizes(fs_size, dino_size)

    def reset(self):
        self._reference.reset()
        self._heatmap.reset()

    def empty_heatmap(self, frame_shape: tuple[int, int]) -> np.ndarray:
        return self._heatmap.empty(frame_shape)

    def process_frame(
        self,
        dino_embedding: dai.NNData,
        frame_sizes: tuple[int, int],
        reference_segmentation: np.ndarray | None,
    ) -> np.ndarray:
        self._reference.tick()

        self._features.begin_frame(dino_embedding)

        if reference_segmentation is not None and not self._reference.has_reference():
            vectors = self._features.reference_vectors_from_segmentation(
                reference_segmentation
            )
            self._reference.initialize_from_vectors(vectors)

        if not self._reference.has_reference():
            return self._heatmap.empty(frame_sizes)

        grid = self._features.get_grid()
        cos_grid = self._reference.compute_similarity(grid)

        return self._heatmap.from_cosine_grid(cos_grid, frame_sizes)
