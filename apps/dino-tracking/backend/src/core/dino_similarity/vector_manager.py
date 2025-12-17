import numpy as np


class VectorManager:
    """
    Stores reference vectors and adapts them over time.

    ReferenceNode: initializes and resets
    SimilarityHeatmapNode: reads references and updates adaptive one
    """

    def __init__(
        self,
        learn_thresh: float = 0.85,
        learn_interval: int = 30,
        learn_blend: float = 0.3,
        combine_alpha: float = 0.7,
    ):
        self._reference_init: np.ndarray | None = None
        self._reference_adapt: np.ndarray | None = None

        self.learn_thresh = learn_thresh
        self.learn_interval = learn_interval
        self.learn_blend = learn_blend
        self.combine_alpha = combine_alpha

        self._frame_idx = 0
        self._last_learn_frame = -(10**9)

    def has_reference(self) -> bool:
        return self._reference_init is not None

    def get_references(self) -> tuple[np.ndarray, np.ndarray]:
        if not self.has_reference():
            raise RuntimeError("Reference not initialized")
        return self._reference_init, self._reference_adapt

    def initialize(self, vectors: np.ndarray) -> None:
        if len(vectors) == 0:
            return

        ref = vectors.mean(axis=0)
        ref = ref / (np.linalg.norm(ref) + 1e-8)

        self._reference_init = ref.astype(np.float32)
        self._reference_adapt = ref.astype(np.float32)
        self._frame_idx = 0
        self._last_learn_frame = -(10**9)

    def reset(self) -> None:
        self._reference_init = None
        self._reference_adapt = None
        self._frame_idx = 0
        self._last_learn_frame = -(10**9)

    def tick(self) -> None:
        self._frame_idx += 1

    def try_update_adaptive(self, best_vector: np.ndarray, best_score: float) -> None:
        if best_score < self.learn_thresh:
            return

        if (self._frame_idx - self._last_learn_frame) < self.learn_interval:
            return

        beta = self.learn_blend
        updated = (1.0 - beta) * self._reference_adapt + beta * best_vector
        updated = updated / (np.linalg.norm(updated) + 1e-8)

        self._reference_adapt = updated.astype(np.float32)
        self._last_learn_frame = self._frame_idx
