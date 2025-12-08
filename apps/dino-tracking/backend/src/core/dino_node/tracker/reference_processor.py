import numpy as np


class ReferenceProcessor:
    """
    Keeps and updates:
      - reference_init  (frozen initial embedding)
      - reference_track (EMA-updated tracking embedding)

    Responsible for:
      - mapping FS-space mask -> DINO grid indices
      - initializing references from the selected region
      - computing cosine grid and adapting reference_track
    """

    def __init__(self):
        self.reference_init: np.ndarray | None = None
        self.reference_track: np.ndarray | None = None

        self.sam_w: int | None = None
        self.sam_h: int | None = None
        self.dino_w: int | None = None
        self.dino_h: int | None = None

        self.learn_thresh: float = 0.85
        self.learn_interval: int = 30
        self.learn_blend: float = 0.3
        self.frame_idx: int = 0
        self.last_learn_frame: int = -10**9

        self.combine_alpha: float = 0.7

    def set_sizes(self, sam_size, dino_size) -> None:
        self.sam_w, self.sam_h = sam_size
        self.dino_w, self.dino_h = dino_size

    def tick_frame(self) -> None:
        self.frame_idx += 1

    def reset(self) -> None:
        self.reference_init = None
        self.reference_track = None
        self.frame_idx = 0
        self.last_learn_frame = -10**9

    def is_ready(self) -> bool:
        return self.reference_init is not None and self.reference_track is not None

    def ensure_initialized(
        self,
        grid: np.ndarray,
        ref_mask_fs: np.ndarray | None,
        logger=None,
    ) -> bool:

        if self.reference_init is not None:
            return True

        if ref_mask_fs is None:
            return True

        if (
            self.sam_w is None
            or self.sam_h is None
            or self.dino_w is None
            or self.dino_h is None
        ):
            if logger:
                logger.warning(
                    "ReferenceProcessor: sizes not set before reference init"
                )
            return False

        H_grid, W_grid, D = grid.shape

        ys, xs = np.where(ref_mask_fs)
        if len(xs) == 0:
            if logger:
                logger.info("ReferenceProcessor: reference mask empty")
            return False

        xs_d = (xs.astype(np.float32) / float(self.sam_w)) * float(self.dino_w)
        ys_d = (ys.astype(np.float32) / float(self.sam_h)) * float(self.dino_h)

        xs_d = np.clip(xs_d, 0, self.dino_w - 1)
        ys_d = np.clip(ys_d, 0, self.dino_h - 1)

        js = (xs_d / float(self.dino_w) * float(W_grid)).astype(np.int32)
        is_ = (ys_d / float(self.dino_h) * float(H_grid)).astype(np.int32)

        js = np.clip(js, 0, W_grid - 1)
        is_ = np.clip(is_, 0, H_grid - 1)

        vectors = grid[is_, js]
        ref = vectors.mean(axis=0)
        ref /= (np.linalg.norm(ref) + 1e-8)
        ref = ref.astype(np.float32)

        self.reference_init = ref.copy()
        self.reference_track = ref.copy()

        if logger:
            logger.info("ReferenceProcessor: reference embeddings initialized")

        return True

    def cosine_grid_and_adapt(self, grid: np.ndarray) -> np.ndarray:
        H_grid, W_grid, D = grid.shape

        feats_flat = grid.reshape(-1, D)
        ref_init = self.reference_init.astype(np.float32)
        ref_track = self.reference_track.astype(np.float32)

        cos_init_flat = feats_flat @ ref_init
        cos_track_flat = feats_flat @ ref_track

        lam = float(self.combine_alpha)
        cos_flat = lam * cos_track_flat + (1.0 - lam) * cos_init_flat

        cos_grid = cos_flat.reshape(H_grid, W_grid).astype(np.float32)

        best_idx = int(np.argmax(cos_track_flat))
        best_val_track = float(cos_track_flat[best_idx])

        if (
            best_val_track >= self.learn_thresh
            and (self.frame_idx - self.last_learn_frame) >= self.learn_interval
        ):
            new_vec = feats_flat[best_idx]
            new_vec = new_vec / (np.linalg.norm(new_vec) + 1e-8)
            new_vec = new_vec.astype(np.float32)

            beta = float(self.learn_blend)
            updated = (1.0 - beta) * self.reference_track + beta * new_vec
            updated /= (np.linalg.norm(updated) + 1e-8)
            self.reference_track = updated.astype(np.float32)

            self.last_learn_frame = self.frame_idx

        return cos_grid
