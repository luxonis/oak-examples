import cv2
import numpy as np
import depthai as dai
from depthai_nodes.node import BaseHostNode


class DinoSegTrackerNode(BaseHostNode):
    """
    Click once on an object (apple, tomato, face, ...).

    Core idea: 2 reference vectors + a bit of "label propagation"-ish behavior.

    References:
      - ref_init: frozen initial embedding (from clicked mask)
      - ref_track: adaptive embedding updated from very confident patches

    Per frame:
      - compute cosine maps to both refs
      - combine them:
          cos = combine_alpha * cos_track + (1 - combine_alpha) * cos_init
      - apply a LOCAL spatial gate around previous object position
      - upsample to full resolution
      - apply absolute cosine threshold
      - light temporal smoothing over the heatmap
    """

    def __init__(self):
        super().__init__()

        # --- References ---
        self.ref_init: np.ndarray | None = None   # (D,)
        self.ref_track: np.ndarray | None = None  # (D,)

        # Mask in FastSAM space defining initial reference region
        self.ref_mask_fs: np.ndarray | None = None  # (H_fs, W_fs) bool

        # Last frames (for click mapping)
        self.last_seg_fs: np.ndarray | None = None
        self.last_seg_full: np.ndarray | None = None
        self.last_frame_full: np.ndarray | None = None

        # DINO + FS sizes
        self.fs_w: int | None = None
        self.fs_h: int | None = None
        self.dino_w: int | None = None
        self.dino_h: int | None = None

        # --- Global cosine threshold (absolute) ---
        # Example: 0.6 ≈ reasonably similar, 0.8 ≈ strict.
        self.sim_thresh: float = 0.6

        # --- Temporal smoothing state (for heatmap) ---
        self.prev_heat: np.ndarray | None = None
        self.temporal_alpha: float = 0.6  # 1.0 = no smoothing

        # --- "Memory" -> reference adaptation (ref_track only) ---
        self.learn_thresh_track: float = 0.85   # cos_track must be >= this
        self.learn_thresh_init: float = 0.80    # cos_init  must be >= this
        self.learn_interval: int = 30           # min frames between ref-updates
        self.learn_blend: float = 0.3           # EMA weight β for ref_track
        self.frame_idx: int = 0
        self.last_learn_frame: int = -10**9
        self.max_adapt_patches: int = 32        # max patches used for an update

        # --- Combination of init + track similarities ---
        # cos = combine_alpha * cos_track + (1 - combine_alpha) * cos_init
        self.combine_alpha: float = 0.7

        # --- Locality window in patch space (baby neighborhood_mask) ---
        # Measured in DINO patch grid cells (not pixels)
        self.last_center_grid: tuple[float, float] | None = None
        self.local_radius_inner: float = 4.0   # inside this → full weight
        self.local_radius_outer: float = 10.0  # beyond this → 0

    # Optional: for FE
    def set_confidence(self, conf: float):
        """
        Set similarity threshold from FE.

        Expected range: 0..1, interpreted directly as cosine similarity threshold.
        """
        self.sim_thresh = float(np.clip(conf, 0.0, 1.0))
        self._logger.info(f"Updated sim_thresh to {self.sim_thresh:.2f}")

    # ------------------------------------------------------------------
    # Wiring
    # ------------------------------------------------------------------
    def build(self, frame_in, seg_in, dino_in, fs_size, dino_size):
        """
        fs_size: (W_fs, H_fs)  from FastSAM model input
        dino_size: (W_dino, H_dino) from DINO model input
        """
        self.link_args(frame_in, seg_in, dino_in)

        self.fs_w, self.fs_h = fs_size
        self.dino_w, self.dino_h = dino_size

        return self

    # ------------------------------------------------------------------
    # CLICK handling (normalized coords from FE)
    # ------------------------------------------------------------------
    def set_selection_click(self, xNorm: float, yNorm: float):
        if self.last_seg_full is None or self.last_seg_fs is None:
            self._logger.info("No segmentation available yet for click")
            return

        H_full, W_full = self.last_seg_full.shape
        x_full = int(xNorm * W_full)
        y_full = int(yNorm * H_full)

        x_full = max(0, min(x_full, W_full - 1))
        y_full = max(0, min(y_full, H_full - 1))

        sid = int(self.last_seg_full[y_full, x_full])

        # Build mask in FS coordinates: this SID in FastSAM space
        self.ref_mask_fs = (self.last_seg_fs == sid)

        # Force recompute of references on next frame
        self.ref_init = None
        self.ref_track = None
        self.prev_heat = None
        self.frame_idx = 0
        self.last_learn_frame = -10**9
        self.last_center_grid = None

        self._logger.info(
            f"Selected SID={sid}, stored reference mask in FS space and reset state"
        )

    def clear_selection(self):
        """Clear current references so tracking stops."""
        self.ref_init = None
        self.ref_track = None
        self.ref_mask_fs = None
        self.prev_heat = None
        self.frame_idx = 0
        self.last_learn_frame = -10**9
        self.last_center_grid = None
        self._logger.info("DinoSegTrackerNode: selection cleared from BE command")

    # ------------------------------------------------------------------
    # DINO grid extraction
    # ------------------------------------------------------------------
    def _extract_patch_grid(self, nn_data: dai.NNData) -> np.ndarray:
        """
        Returns (H_grid, W_grid, D) array of L2-normalized feature vectors.
        """
        arr = nn_data.getTensor(
            "embeddings",
            dequantize=True,
            storageOrder=dai.TensorInfo.StorageOrder.NCHW,
        )
        # arr: (1, C, H, W)
        feats = arr.transpose(0, 3, 1, 2)  # -> (1, H, W, C)
        feats = feats.reshape(-1, feats.shape[3]).astype(np.float32)

        # L2 normalize per patch
        feats /= (np.linalg.norm(feats, axis=1, keepdims=True) + 1e-8)

        # Back to (H_grid, W_grid, D)
        return feats.reshape(arr.shape[3], arr.shape[1], arr.shape[2])  # (H_grid, W_grid, D)

    # ------------------------------------------------------------------
    # Init reference vectors once after click
    # ------------------------------------------------------------------
    def _init_refs_from_mask(self, grid: np.ndarray):
        """
        Initialize ref_init and ref_track as the mean embedding inside the clicked FS mask.
        """
        if self.ref_mask_fs is None:
            return

        H_grid, W_grid, D = grid.shape

        ys_fs, xs_fs = np.where(self.ref_mask_fs)
        if ys_fs.size == 0:
            self._logger.info("Reference mask empty; cannot init references")
            self.ref_init = None
            self.ref_track = None
            return

        # FS -> DINO input
        xs_d = (xs_fs.astype(np.float32) / float(self.fs_w)) * float(self.dino_w)
        ys_d = (ys_fs.astype(np.float32) / float(self.fs_h)) * float(self.dino_h)

        xs_d = np.clip(xs_d, 0, self.dino_w - 1)
        ys_d = np.clip(ys_d, 0, self.dino_h - 1)

        # DINO input -> patch grid indices
        js = (xs_d / float(self.dino_w) * float(W_grid)).astype(np.int32)
        is_ = (ys_d / float(self.dino_h) * float(H_grid)).astype(np.int32)

        js = np.clip(js, 0, W_grid - 1)
        is_ = np.clip(is_, 0, H_grid - 1)

        vectors = grid[is_, js]          # (N, D) normalized
        if vectors.size == 0:
            self._logger.info("No vectors inside reference mask; cannot init references")
            self.ref_init = None
            self.ref_track = None
            return

        ref = vectors.mean(axis=0)
        ref /= (np.linalg.norm(ref) + 1e-8)
        ref = ref.astype(np.float32)

        self.ref_init = ref.copy()
        self.ref_track = ref.copy()

        # Also initialize center in grid space from these coordinates
        cy = float(is_.mean())
        cx = float(js.mean())
        self.last_center_grid = (cy, cx)

        self._logger.info(
            f"Reference DINO embeddings initialized (N={vectors.shape[0]}) "
            f"and center_grid={self.last_center_grid}"
        )

    # ------------------------------------------------------------------
    # Build locality gate in patch space
    # ------------------------------------------------------------------
    def _apply_local_gate(self, cos: np.ndarray) -> np.ndarray:
        """
        Apply a soft radial gate around last_center_grid in (H_grid, W_grid) space.

        Inside radius_inner  -> weight 1
        Between inner/outer  -> linear decay 1..0
        Outside radius_outer -> weight 0
        """
        if self.last_center_grid is None:
            return cos

        H_grid, W_grid = cos.shape
        cy, cx = self.last_center_grid

        yy, xx = np.meshgrid(
            np.arange(H_grid, dtype=np.float32),
            np.arange(W_grid, dtype=np.float32),
            indexing="ij",
        )
        dy = yy - cy
        dx = xx - cx
        dist = np.sqrt(dy * dy + dx * dx)

        r1 = float(self.local_radius_inner)
        r2 = float(self.local_radius_outer)
        if r2 <= r1:
            return cos  # misconfig, just skip

        gate = np.ones_like(cos, dtype=np.float32)

        # Outside outer radius -> 0
        gate[dist >= r2] = 0.0

        # Between inner and outer: linear fade
        mask_mid = (dist >= r1) & (dist < r2)
        gate[mask_mid] = 1.0 - (dist[mask_mid] - r1) / (r2 - r1)

        # Multiply cosine map by gate
        return cos * gate

    # ------------------------------------------------------------------
    # Update last_center_grid from current heatmap in grid space
    # ------------------------------------------------------------------
    def _update_center_from_cos(self, cos: np.ndarray):
        """
        Update object center from positive cosine values in patch space.
        Uses cosine as weights (only > sim_thresh).
        """
        mask = cos >= self.sim_thresh
        if not np.any(mask):
            return  # keep old center; we lost object this frame

        weights = cos * mask.astype(np.float32)
        total = float(weights.sum())
        if total <= 1e-8:
            return

        H_grid, W_grid = cos.shape
        yy, xx = np.meshgrid(
            np.arange(H_grid, dtype=np.float32),
            np.arange(W_grid, dtype=np.float32),
            indexing="ij",
        )
        cy = float((yy * weights).sum() / total)
        cx = float((xx * weights).sum() / total)
        self.last_center_grid = (cy, cx)

    # ------------------------------------------------------------------
    # MAIN Frame loop
    # ------------------------------------------------------------------
    def process(self, frame_msg, seg_msg, dino_msg):
        self.frame_idx += 1

        frame_full = frame_msg.getCvFrame()
        H_full, W_full = frame_full.shape[:2]

        # FastSAM segmentation (FS resolution) – only for click mapping
        seg_fs = seg_msg.mask.astype(np.int32)
        self.last_seg_fs = seg_fs

        # Full-res seg (for click mapping)
        seg_full = cv2.resize(seg_fs, (W_full, H_full), interpolation=cv2.INTER_NEAREST)
        self.last_seg_full = seg_full
        self.last_frame_full = frame_full

        # DINO patch grid
        grid = self._extract_patch_grid(dino_msg)  # (H_grid, W_grid, D)
        H_grid, W_grid, D = grid.shape

        # 1) Compute reference embeddings once from reference mask
        if self.ref_init is None and self.ref_mask_fs is not None:
            self._init_refs_from_mask(grid)

        # No reference yet → flat zero heatmap
        if self.ref_init is None or self.ref_track is None:
            self.prev_heat = None
            self._send_heatmap(frame_msg, np.zeros((H_full, W_full), dtype=np.float32))
            return

        # 2) Cosine similarity maps for BOTH references
        feats_flat = grid.reshape(-1, D).astype(np.float32)  # (N, D), normalized

        ref_init = self.ref_init.astype(np.float32)          # (D,)
        ref_track = self.ref_track.astype(np.float32)        # (D,)

        cos_init_flat = feats_flat @ ref_init                # (N,)
        cos_track_flat = feats_flat @ ref_track              # (N,)

        lam = float(self.combine_alpha)
        cos_flat = lam * cos_track_flat + (1.0 - lam) * cos_init_flat  # (N,)

        cos = cos_flat.reshape(H_grid, W_grid)               # (H_grid, W_grid)

        # 3) Apply local spatial gate (baby neighborhood_mask)
        cos = self._apply_local_gate(cos)

        # 4) Update center from this cosine map (for next frame)
        self._update_center_from_cos(cos)

        # 5) Upsample to full frame resolution
        cos_full = cv2.resize(
            cos,
            (W_full, H_full),
            interpolation=cv2.INTER_LINEAR,
        ).astype(np.float32)

        # Optional spatial smoothing (neighborhood consistency)
        cos_full = cv2.GaussianBlur(cos_full, (5, 5), 0)

        # 6) REFERENCE ADAPTATION (ref_track only) using multiple hot patches
        if (self.frame_idx - self.last_learn_frame) >= self.learn_interval:
            hot_mask = (
                (cos_track_flat >= self.learn_thresh_track)
                & (cos_init_flat >= self.learn_thresh_init)
            )
            hot_indices = np.nonzero(hot_mask)[0]

            if hot_indices.size > 0:
                # Sort by cos_track descending and take top K
                if hot_indices.size > self.max_adapt_patches:
                    order = np.argsort(cos_track_flat[hot_indices])[::-1]
                    hot_indices = hot_indices[order[: self.max_adapt_patches]]

                hot_vecs = feats_flat[hot_indices]  # (K, D)
                new_vec = hot_vecs.mean(axis=0)
                new_vec /= (np.linalg.norm(new_vec) + 1e-8)
                new_vec = new_vec.astype(np.float32)

                beta = float(self.learn_blend)
                updated = (1.0 - beta) * self.ref_track + beta * new_vec
                updated /= (np.linalg.norm(updated) + 1e-8)
                self.ref_track = updated.astype(np.float32)

                self.last_learn_frame = self.frame_idx
                self._logger.info(
                    f"Adapted ref_track (K={hot_vecs.shape[0]}, "
                    f"frame={self.frame_idx})"
                )

        # 7) ABSOLUTE cosine threshold
        if self.sim_thresh > -1.0:
            heat = np.where(cos_full >= self.sim_thresh, cos_full, 0.0)
        else:
            heat = cos_full

        heat_clipped = np.clip(heat, 0.0, 1.0).astype(np.float32)

        # 8) TEMPORAL SMOOTHING
        if np.any(heat_clipped > 0.0):
            if self.prev_heat is None or self.prev_heat.shape != heat_clipped.shape:
                blended = heat_clipped
            else:
                a = float(self.temporal_alpha)
                blended = a * heat_clipped + (1.0 - a) * self.prev_heat
        else:
            blended = np.zeros_like(heat_clipped, dtype=np.float32)

        self.prev_heat = blended
        self._send_heatmap(frame_msg, blended)

    # ------------------------------------------------------------------
    # Helper: send float heatmap as ImgFrame (0/255, same in all channels)
    # ------------------------------------------------------------------
    def _send_heatmap(self, ref_msg: dai.ImgFrame, heat: np.ndarray):
        heat_clipped = np.clip(heat, 0.0, 1.0)
        heat_u8 = (heat_clipped * 255.0).astype(np.uint8)
        heat_bgr = cv2.merge([heat_u8, heat_u8, heat_u8])

        out = dai.ImgFrame()
        out.setCvFrame(heat_bgr, self._img_frame_type)
        out.setSequenceNum(ref_msg.getSequenceNum())
        out.setTimestamp(ref_msg.getTimestamp())
        out.setTimestampDevice(ref_msg.getTimestampDevice())
        self.out.send(out)
