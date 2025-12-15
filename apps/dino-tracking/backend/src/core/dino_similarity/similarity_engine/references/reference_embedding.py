import numpy as np


class ReferenceEmbedding:
    """
    Handles:
      - initialization from feature vectors
      - normalization
      - cosine similarity grid computation
      - finding best-match vector
    """

    @staticmethod
    def normalize(v: np.ndarray) -> np.ndarray:
        return v / (np.linalg.norm(v) + 1e-8)

    def initialize_from_vectors(self, vectors: np.ndarray) -> np.ndarray:
        if len(vectors) == 0:
            return None

        ref = vectors.mean(axis=0)
        ref = self.normalize(ref.astype(np.float32))
        return ref

    def cosine_grid(
        self,
        grid: np.ndarray,
        reference_init: np.ndarray,
        reference_adapt: np.ndarray,
        alpha: float,
    ) -> tuple[np.ndarray, int, float]:
        H, W, D = grid.shape
        feats = grid.reshape(-1, D).astype(np.float32)

        cos_init = feats @ reference_init.astype(np.float32)
        cos_track = feats @ reference_adapt.astype(np.float32)

        cos = alpha * cos_track + (1.0 - alpha) * cos_init
        cos_grid = cos.reshape(H, W).astype(np.float32)

        best_idx = int(np.argmax(cos_track))
        best_val_track = float(cos_track[best_idx])

        best_vector = self.best_vector(grid, best_idx)

        return cos_grid, best_vector, best_val_track

    def best_vector(self, grid: np.ndarray, best_idx: int) -> np.ndarray:
        feats = grid.reshape(-1, grid.shape[-1]).astype(np.float32)
        vec = feats[best_idx]
        return self.normalize(vec)
