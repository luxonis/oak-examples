import cv2
import numpy as np
from collections import deque  # deque not strictly needed anymore, but fine

import depthai as dai
from depthai_nodes.node import BaseHostNode


class DinoSegTrackerNode(BaseHostNode):
    """
    Click once on an object (apple, tomato, face, ...).

    Per frame:
      - compute cosine map between DINO patches and TWO tracking vectors:
          * ref_init: frozen initial reference from the click
          * ref_track: adaptive reference updated from confident patches
      - combine similarities:
          cos = combine_alpha * cos_track + (1 - combine_alpha) * cos_init
      - upsample cosine grid to full-res
      - optional light temporal smoothing over the heatmap
      - output heatmap (0..255) in all 3 channels

    IMPORTANT:
      - NO thresholding / hysteresis / region growing here.
      - We just output the raw (clipped-to-[0,1]) similarity field.
      - All thresholding and blob extraction is done in the annotation node.
    """

    def __init__(self):
        super().__init__()

        # --- References ---
        # ref_init: frozen initial embedding (from click / segment)
        # ref_track: adaptive tracking embedding (EMA-updated)
        self.ref_init: np.ndarray | None = None   # (D,)
        self.ref_track: np.ndarray | None = None  # (D,)
        # Mask in FastSAM space defining initial reference region
        self.ref_mask_fs: np.ndarray | None = None  # (H_fs, W_fs) bool

        # Last frames (for click mapping)
        self.last_seg_fs: np.ndarray | None = None
        self.last_seg_full: np.ndarray | None = None
        self.last_frame_full: np.ndarray | None = None

        # Sizes
        self.fs_w: int | None = None
        self.fs_h: int | None = None
        self.dino_w: int | None = None
        self.dino_h: int | None = None

        # --- Temporal smoothing state (for heatmap) ---
        self.prev_heat: np.ndarray | None = None
        self.temporal_alpha: float = 0.6  # 1.0 = no smoothing

        # --- Lightweight "memory" -> reference adaptation (ref_track only) ---
        self.learn_thresh: float = 0.85     # gate: only very confident patches update ref_track
        self.learn_interval: int = 30       # min frames between ref-updates
        self.learn_blend: float = 0.3       # EMA weight β for ref_track
        self.frame_idx: int = 0
        self.last_learn_frame: int = -10**9

        # --- Combination of init + track similarities (option B) ---
        # cos = combine_alpha * cos_track + (1 - combine_alpha) * cos_init
        self.combine_alpha: float = 0.7

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
        self._logger.info(
            f"Received selection click at normalized coords: ({xNorm}, {yNorm})"
        )

        if self.last_seg_full is None or self.last_seg_fs is None:
            self._logger.info("No segmentation available yet for click")
            return

        H_full, W_full = self.last_seg_full.shape

        x_full = int(xNorm * W_full)
        y_full = int(yNorm * H_full)

        x_full = max(0, min(x_full, W_full - 1))
        y_full = max(0, min(y_full, H_full - 1))

        # --- Robust SID selection: majority vote in a small window ---
        R = 2  # radius in pixels (window size = (2R+1) x (2R+1))
        x0 = max(0, x_full - R)
        x1 = min(W_full, x_full + R + 1)
        y0 = max(0, y_full - R)
        y1 = min(H_full, y_full + R + 1)

        patch = self.last_seg_full[y0:y1, x0:x1]
        if patch.size == 0:
            self._logger.info("Click patch empty; ignoring")
            return

        vals, counts = np.unique(patch, return_counts=True)
        sid = int(vals[np.argmax(counts)])

        self._logger.info(
            f"Click at ({x_full}, {y_full}) -> majority SID={sid} "
            f"in window x[{x0}:{x1}), y[{y0}:{y1})"
        )

        # Build mask in FS coordinates: this SID in FastSAM space
        self.ref_mask_fs = (self.last_seg_fs == sid)

        # Force recompute of references on next frame
        self.ref_init = None
        self.ref_track = None
        self.prev_heat = None
        self.frame_idx = 0
        self.last_learn_frame = -10 ** 9

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
        self._logger.info("DinoSegTrackerNode: selection cleared from BE command")

    # ------------------------------------------------------------------
    # DINO grid extraction
    # ------------------------------------------------------------------
    def _extract_patch_grid(self, nn_data: dai.NNData) -> np.ndarray:
        """
        Returns (H_grid, W_grid, D) array of L2-normalized feature vectors.

        NOTE: this keeps your original (working) shape logic.
        """
        arr = nn_data.getTensor(
            "embeddings",
            dequantize=True,
            storageOrder=dai.TensorInfo.StorageOrder.NCHW,
        )
        # arr: (1, C, H, W)
        feats = arr.transpose(0, 3, 1, 2)  # -> (1, H, W, C)
        feats = feats.reshape(-1, feats.shape[3])

        # L2 normalize per patch
        feats /= (np.linalg.norm(feats, axis=1, keepdims=True) + 1e-8)

        # Back to (H_grid, W_grid, D)
        return feats.reshape(arr.shape[3], arr.shape[1], arr.shape[2])  # (H_grid, W_grid, D)

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

        # --------------------------------------------------------------
        # 1) Compute reference embeddings ONCE from reference mask
        #    - ref_init: frozen original
        #    - ref_track: adaptive (starts equal to ref_init)
        # --------------------------------------------------------------
        if self.ref_init is None and self.ref_mask_fs is not None:
            ys, xs = np.where(self.ref_mask_fs)   # FS coords
            if len(xs) == 0:
                self._logger.info("Reference mask empty; sending empty heatmap")
                self.prev_heat = None
                self._send_heatmap(frame_msg, np.zeros((H_full, W_full), dtype=np.float32))
                return

            # FS -> DINO input
            xs_d = (xs.astype(np.float32) / float(self.fs_w)) * float(self.dino_w)
            ys_d = (ys.astype(np.float32) / float(self.fs_h)) * float(self.dino_h)

            xs_d = np.clip(xs_d, 0, self.dino_w - 1)
            ys_d = np.clip(ys_d, 0, self.dino_h - 1)

            # DINO input -> patch grid
            js = (xs_d / float(self.dino_w) * float(W_grid)).astype(np.int32)
            is_ = (ys_d / float(self.dino_h) * float(H_grid)).astype(np.int32)

            js = np.clip(js, 0, W_grid - 1)
            is_ = np.clip(is_, 0, H_grid - 1)

            vectors = grid[is_, js]          # (N, D) normalized
            ref = vectors.mean(axis=0)
            ref /= (np.linalg.norm(ref) + 1e-8)
            ref = ref.astype(np.float32)

            self.ref_init = ref.copy()
            self.ref_track = ref.copy()

            self._logger.info("Reference DINO embeddings initialized (init + track)")

        # No reference yet → flat zero heatmap
        if self.ref_init is None or self.ref_track is None:
            self.prev_heat = None
            self._send_heatmap(frame_msg, np.zeros((H_full, W_full), dtype=np.float32))
            return

        # --------------------------------------------------------------
        # 2) Cosine similarity maps for BOTH references
        # --------------------------------------------------------------
        feats_flat = grid.reshape(-1, D)                     # (N, D)
        ref_init = self.ref_init.astype(np.float32)          # (D,)
        ref_track = self.ref_track.astype(np.float32)        # (D,)

        cos_init_flat = feats_flat @ ref_init                # (N,)
        cos_track_flat = feats_flat @ ref_track              # (N,)

        # Weighted combination (option B)
        lam = float(self.combine_alpha)
        cos_flat = lam * cos_track_flat + (1.0 - lam) * cos_init_flat  # (N,)

        # Grid cosine map (can be negative, up to ~1.0)
        cos_grid = cos_flat.reshape(H_grid, W_grid).astype(np.float32)

        # --------------------------------------------------------------
        # 3) REFERENCE ADAPTATION (ref_track only)
        # --------------------------------------------------------------
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
            updated = (1.0 - beta) * self.ref_track + beta * new_vec
            updated /= (np.linalg.norm(updated) + 1e-8)
            self.ref_track = updated.astype(np.float32)

            self.last_learn_frame = self.frame_idx
            self._logger.info(
                f"Adapted ref_track (best cos_track={best_val_track:.2f}, "
                f"learn_thresh={self.learn_thresh:.2f}, frame={self.frame_idx})"
            )

        # --------------------------------------------------------------
        # 4) UPSAMPLE TO FULL-RES (NO THRESHOLDING HERE)
        # --------------------------------------------------------------
        heat_grid = cos_grid  # raw cosine similarities

        heat_full = cv2.resize(
            heat_grid,
            (W_full, H_full),
            interpolation=cv2.INTER_LINEAR,
        ).astype(np.float32)

        # Clip to [0,1] for visualization (negatives → 0, positives up to 1)
        heat_clipped = np.clip(heat_full, 0.0, 1.0).astype(np.float32)

        # --------------------------------------------------------------
        # 5) TEMPORAL SMOOTHING (optional; currently disabled)
        # --------------------------------------------------------------
        if np.any(heat_clipped > 0.0):
            if self.prev_heat is None or self.prev_heat.shape != heat_clipped.shape:
                blended = heat_clipped
            else:
                a = float(self.temporal_alpha)
                blended = a * heat_clipped + (1.0 - a) * self.prev_heat
        else:
            blended = np.zeros_like(heat_clipped, dtype=np.float32)

        # If you want smoothing, remove this line, otherwise keep "as is"
        blended = heat_clipped

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
