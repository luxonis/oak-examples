import numpy as np
from core.dino_similarity.similarity_engine.references.reference_adaptation_state import ReferenceAdaptationState
from core.dino_similarity.similarity_engine.references.reference_embedding import ReferenceEmbedding


class ReferenceSystem:
    """
    Owns reference initialization, adaptation, and similarity scoring.
    """

    def __init__(self):
        self._embedding = ReferenceEmbedding()
        self._adaptation_state = ReferenceAdaptationState()

    def reset(self):
        self._adaptation_state.reset()

    def tick(self):
        self._adaptation_state.tick()

    def initialize_from_vectors(self, vectors: np.ndarray):
        ref = self._embedding.initialize_from_vectors(vectors)
        if ref is not None:
            self._adaptation_state.initialize(ref)

    def has_reference(self) -> bool:
        return self._adaptation_state.has_reference()

    def compute_similarity(self, grid: np.ndarray):
        cos_grid, best_vec, best_val = self._embedding.cosine_grid(
            grid,
            self._adaptation_state.reference_init,
            self._adaptation_state.reference_adapt,
            self._adaptation_state.combine_alpha,
        )

        self._adaptation_state.update_adapting_reference(best_vec, best_val)

        return cos_grid
