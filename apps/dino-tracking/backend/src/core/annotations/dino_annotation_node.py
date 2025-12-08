import cv2
import numpy as np
import depthai as dai
from depthai_nodes.node.base_host_node import BaseHostNode


class DinoAnnotationNode(BaseHostNode):
    """
    Handles visual annotations for Dino tracking results using two modes:
    - "heatmap": green translucent overlay based on tracker heatmap
    - "bbox": bounding boxes around detected hot blobs
    """

    def __init__(self, mode: str = "heatmap"):
        super().__init__()
        self.mode = mode
        self.bbox_conf_thresh = 0.5
        self.bbox_min_area = 50
        self.bbox_max_boxes = 6

    def build(self, video_in, seg_in, mask_in):
        self.link_args(video_in, seg_in, mask_in)
        return self

    def set_mode(self, mode: str):
        if mode in ["heatmap", "bbox"]:
            self.mode = mode
            self._logger.info(f"DinoAnnotationNode mode set to '{mode}'")

    def set_confidence(self, conf: float):
        self.bbox_conf_thresh = float(np.clip(float(conf), 0.0, 1.0))
        self._logger.info(f"DinoAnnotationNode: bbox_conf_thresh set to {self.bbox_conf_thresh:.2f}")

    def process(self, video_msg, seg_msg, mask_msg):
        frame = video_msg.getCvFrame()
        H, W = frame.shape[:2]

        mask = mask_msg.getCvFrame()
        mask_gray = mask[..., 0] if mask.ndim == 3 else mask

        if mask_gray.shape != (H, W):
            mask_gray = cv2.resize(mask_gray, (W, H), interpolation=cv2.INTER_NEAREST)
        mask_gray = mask_gray.astype(np.uint8)

        if not np.any(mask_gray):
            self._send(frame, video_msg)
            return

        if self.mode == "heatmap":
            self._annot_heatmap(frame, mask_gray, video_msg)
            return

        if self.mode == "bbox":
            self._annot_bbox(frame, mask_gray, video_msg)
            return

        self._send(frame, video_msg)

    def _annot_heatmap(self, frame, mask_gray, video_msg):
        heat = mask_gray.astype(np.float32) / 255.0
        heat_color = np.zeros_like(frame, dtype=np.uint8)
        heat_color[..., 1] = mask_gray
        alpha = (heat * 0.6)[..., None]
        result = (frame * (1 - alpha) + heat_color * alpha).astype(np.uint8)
        self._send(result, video_msg)

    def _annot_bbox(self, frame, mask_gray, video_msg):
        heat = mask_gray.astype(np.float32) / 255.0
        if heat.max() <= 0:
            self._send(frame, video_msg)
            return

        blobs, stats = self._extract_blobs(heat, self.bbox_conf_thresh)
        if not blobs:
            self._send(frame, video_msg)
            return

        result = frame.copy()
        for lbl, area in blobs:
            x = int(stats[lbl, cv2.CC_STAT_LEFT])
            y = int(stats[lbl, cv2.CC_STAT_TOP])
            w = int(stats[lbl, cv2.CC_STAT_WIDTH])
            h = int(stats[lbl, cv2.CC_STAT_HEIGHT])
            cv2.rectangle(result, (x, y), (x + w, y + h), (0, 255, 0), 2)

        self._send(result, video_msg)

    def _extract_blobs(self, heat, thr):
        hot = (heat >= thr).astype(np.uint8)
        kernel = np.ones((3, 3), np.uint8)
        hot = cv2.morphologyEx(hot, cv2.MORPH_OPEN, kernel)
        hot = cv2.dilate(hot, kernel, iterations=1)

        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(hot, connectivity=8)

        blobs = []
        for lbl in range(1, num_labels):
            area = int(stats[lbl, cv2.CC_STAT_AREA])
            if area < self.bbox_min_area:
                continue
            blob_mask = (labels == lbl)
            if float(heat[blob_mask].max()) < thr:
                continue
            blobs.append((lbl, area))

        blobs.sort(key=lambda x: x[1], reverse=True)
        return blobs[: self.bbox_max_boxes], stats

    def _send(self, frame: np.ndarray, ref_msg: dai.ImgFrame):
        out = dai.ImgFrame()
        out.setCvFrame(frame, self._img_frame_type)
        out.setSequenceNum(ref_msg.getSequenceNum())
        out.setTimestamp(ref_msg.getTimestamp())
        out.setTimestampDevice(ref_msg.getTimestampDevice())
        self.out.send(out)
