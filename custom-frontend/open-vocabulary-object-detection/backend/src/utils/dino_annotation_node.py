import cv2
import numpy as np
import depthai as dai
from depthai_nodes.node.base_host_node import BaseHostNode


class DinoAnnotationNode(BaseHostNode):
    """
    Inputs:
      - video_in: ImgFrame (BGR) from OutlinesOverlayNode
      - seg_in:   FastSAM segmentation (SID mask)
      - mask_in:  heatmap from DinoSegTrackerNode (ImgFrame, BGR, 0..255)

    Modes:
      - "segments":  FastSAM segments which overlap any hot region in the heatmap
      - "heatmap":   mask acts as intensity for a green heat overlay
      - "bbox":      tight bounding boxes around hot blobs in heatmap
    """

    def __init__(self, mode: str = "heatmap"):
        super().__init__()
        self.mode = mode

        # BBox tuning params (for "bbox" mode)
        self.bbox_rel_thresh = 0.5   # keep pixels >= 50% of max heat
        self.bbox_min_area = 50      # ignore tiny blobs
        self.bbox_max_boxes = 6      # draw at most N bboxes

        # Segment selection params (for "segments" mode)
        self.seg_min_area = 80          # ignore tiny segments
        self.seg_ignore_sid_zero = True # 0 = background for FastSAM

    def build(self, video_in, seg_in, mask_in):
        self.link_args(video_in, seg_in, mask_in)
        return self

    # ------------------------------------------------------------------
    # Main processing
    # ------------------------------------------------------------------
    def process(self, video_msg, seg_msg, mask_msg):
        frame = video_msg.getCvFrame()
        H, W = frame.shape[:2]

        # --- Heatmap from tracker ---
        mask_frame = mask_msg.getCvFrame()
        if mask_frame.ndim == 3:
            mask_gray = mask_frame[..., 0]
        else:
            mask_gray = mask_frame

        if mask_gray.shape != (H, W):
            mask_gray = cv2.resize(mask_gray, (W, H), interpolation=cv2.INTER_NEAREST)
        mask_gray = mask_gray.astype(np.uint8)

        if not np.any(mask_gray):
            # No hot pixels at all – tracker says "nothing similar"
            self._send(frame, video_msg)
            return

        mode = self.mode

        # ----------------------------------------------------------
        # MODE 1: segments (FastSAM segments overlapping heat)
        # ----------------------------------------------------------
        if mode == "segments":
            try:
                seg_fs = seg_msg.mask.astype(np.int32)
            except AttributeError:
                # No segmentation available – fall back to simple heat mask
                selected = mask_gray > 0
                highlight = np.zeros_like(frame)
                highlight[selected] = (0, 255, 0)
                result = cv2.addWeighted(frame, 1.0, highlight, 0.45, 0.0)
                self._send(result, video_msg)
                return

            # Resize segmentation to match video size
            seg_full = cv2.resize(seg_fs, (W, H), interpolation=cv2.INTER_NEAREST)

            # Heat in [0,1]
            heat = mask_gray.astype(np.float32) / 255.0

            # Candidate SIDs (skip 0 if background)
            candidate_sids = np.unique(seg_full)
            candidate_sids = [int(sid) for sid in candidate_sids]

            selected_mask = np.zeros((H, W), dtype=bool)
            min_area = self.seg_min_area
            selected_sids = []

            for sid in candidate_sids:
                sid_mask = (seg_full == sid)
                area = int(np.count_nonzero(sid_mask))
                if area < min_area:
                    continue

                sid_heat = heat[sid_mask]

                # Segment ON if any pixel passed sim_thresh in tracker
                if np.any(sid_heat > 0.0):
                    selected_mask |= sid_mask
                    selected_sids.append(sid)

            self._logger.info(
                f"DinoAnnotationNode segments: candidates={len(candidate_sids)}, "
                f"selected={len(selected_sids)} -> {selected_sids}"
            )

            if not np.any(selected_mask):
                # Heat exists but does not overlap any big segment
                self._send(frame, video_msg)
                return

            highlight = np.zeros_like(frame)
            highlight[selected_mask] = (0, 255, 0)

            result = cv2.addWeighted(frame, 1.0, highlight, 0.45, 0.0)
            self._send(result, video_msg)
            return

        # ----------------------------------------------------------
        # MODE 2: heatmap overlay (mask as intensity)
        # ----------------------------------------------------------
        if mode == "heatmap":
            heat_norm = np.clip(mask_gray.astype(np.float32) / 255.0, 0.0, 1.0)

            heat_color = np.zeros_like(frame, dtype=np.uint8)
            heat_color[..., 1] = mask_gray  # G channel gets intensity

            alpha = (heat_norm * 0.6)[..., None].astype(np.float32)

            result = (
                frame.astype(np.float32) * (1.0 - alpha)
                + heat_color.astype(np.float32) * alpha
            )
            result = result.astype(np.uint8)

            self._send(result, video_msg)
            return

        # ----------------------------------------------------------
        # MODE 3: bbox (tight rectangles around hot blobs)
        # ----------------------------------------------------------
        if mode == "bbox":
            heat = mask_gray.astype(np.float32) / 255.0
            m = float(heat.max())
            if m <= 0.0:
                self._send(frame, video_msg)
                return

            thr = self.bbox_rel_thresh * m
            hot = (heat >= thr).astype(np.uint8)

            kernel = np.ones((3, 3), np.uint8)
            hot = cv2.morphologyEx(hot, cv2.MORPH_OPEN, kernel)
            hot = cv2.dilate(hot, kernel, iterations=1)

            num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
                hot, connectivity=8
            )

            if num_labels <= 1:
                self._send(frame, video_msg)
                return

            blobs = []
            for lbl in range(1, num_labels):
                area = int(stats[lbl, cv2.CC_STAT_AREA])
                if area < self.bbox_min_area:
                    continue
                blobs.append((lbl, area))

            if not blobs:
                self._send(frame, video_msg)
                return

            blobs.sort(key=lambda x: x[1], reverse=True)
            blobs = blobs[: self.bbox_max_boxes]

            result = frame.copy()
            for lbl, area in blobs:
                x = int(stats[lbl, cv2.CC_STAT_LEFT])
                y = int(stats[lbl, cv2.CC_STAT_TOP])
                w = int(stats[lbl, cv2.CC_STAT_WIDTH])
                h = int(stats[lbl, cv2.CC_STAT_HEIGHT])
                cv2.rectangle(result, (x, y), (x + w, y + h), (0, 255, 0), 2)

            self._send(result, video_msg)
            return

        # ----------------------------------------------------------
        # Fallback: unknown mode → just forward frame
        # ----------------------------------------------------------
        self._logger.warning(
            f"DinoAnnotationNode: unknown mode '{mode}', forwarding frame"
        )
        self._send(frame, video_msg)

    def _send(self, frame: np.ndarray, ref_msg: dai.ImgFrame):
        out = dai.ImgFrame()
        out.setCvFrame(frame, self._img_frame_type)
        out.setSequenceNum(ref_msg.getSequenceNum())
        out.setTimestamp(ref_msg.getTimestamp())
        out.setTimestampDevice(ref_msg.getTimestampDevice())
        self.out.send(out)

    def set_mode(self, mode: str):
        if mode in ["segments", "heatmap", "bbox"]:
            self.mode = mode
            self._logger.info(f"DinoAnnotationNode mode set to '{mode}'")
        else:
            self._logger.warning(
                f"DinoAnnotationNode: invalid mode '{mode}'"
            )
