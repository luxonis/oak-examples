import numpy as np
from core.dino_node.tracker.references.reference_adaptation_state import ReferenceAdaptationState
from core.dino_node.tracker.references.reference_embedding import ReferenceEmbedding


class ReferenceSystem:
    """
    Owns reference initialization, adaptation, and similarity scoring.
    """

    def __init__(self):
        self._embedding = ReferenceEmbedding()
        self._tracker = ReferenceAdaptationState()

    def reset(self):
        self._tracker.reset()

    def tick(self):
        self._tracker.tick()

    def initialize_from_vectors(self, vectors: np.ndarray):
        ref = self._embedding.initialize_from_vectors(vectors)
        if ref is not None:
            self._tracker.initialize(ref)

    def has_reference(self) -> bool:
        return self._tracker.has_reference()

    def compute_similarity(self, grid: np.ndarray):
        cos_grid, best_idx, best_val = self._embedding.cosine_grid(
            grid,
            self._tracker.reference_init,
            self._tracker.reference_track,
            self._tracker.combine_alpha,
        )

        best_vec = self._embedding.best_vector(grid, best_idx)
        self._tracker.update_tracking_reference(best_vec, best_val)

        return cos_grid
