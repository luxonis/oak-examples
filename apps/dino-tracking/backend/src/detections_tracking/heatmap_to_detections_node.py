import cv2
import depthai as dai
import numpy as np
from depthai_nodes.node.base_host_node import BaseHostNode


class HeatmapToDetections(BaseHostNode):
    """
    Converts heatmap into ImgDetections.
    """

    def __init__(
        self,
        min_area: int = 50,
    ):
        super().__init__()
        self._conf_threshold = 0.5
        self._min_area = min_area

    def set_confidence_threshold(self, conf_thresh: float):
        self._conf_threshold = conf_thresh

    def get_confidence_threshold(self) -> float:
        return self._conf_threshold

    def build(self, heatmap_in: dai.Node.Output):
        self.link_args(heatmap_in)
        return self

    def process(self, heatmap_msg: dai.Buffer):
        assert isinstance(heatmap_msg, dai.ImgFrame)
        mask = heatmap_msg.getCvFrame()
        mask_gray = mask[..., 0] if mask.ndim == 3 else mask

        H, W = mask_gray.shape[:2]
        heat = mask_gray.astype(np.float32) / 255.0

        detections = dai.ImgDetections()

        detections.setSequenceNum(heatmap_msg.getSequenceNum())
        detections.setTimestamp(heatmap_msg.getTimestamp())
        detections.setTimestampDevice(heatmap_msg.getTimestampDevice())

        if heat.max() <= 0:
            self.out.send(detections)
            return

        blobs, stats = self._extract_blobs(heat)

        det_list = []
        for lbl, _area in blobs:
            x = int(stats[lbl, cv2.CC_STAT_LEFT])
            y = int(stats[lbl, cv2.CC_STAT_TOP])
            w = int(stats[lbl, cv2.CC_STAT_WIDTH])
            h = int(stats[lbl, cv2.CC_STAT_HEIGHT])

            conf = float(heat[y : y + h, x : x + w].max())

            det = dai.ImgDetection()
            det.label = 0
            det.confidence = conf
            det.xmin = x / W
            det.ymin = y / H
            det.xmax = (x + w) / W
            det.ymax = (y + h) / H

            det_list.append(det)

        detections.detections = det_list

        self.out.send(detections)

    def _extract_blobs(self, heat: np.ndarray):
        hot = (heat >= self._conf_threshold).astype(np.uint8)

        kernel = np.ones((3, 3), np.uint8)
        hot = cv2.morphologyEx(hot, cv2.MORPH_OPEN, kernel)
        hot = cv2.dilate(hot, kernel, iterations=1)

        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
            hot, connectivity=8
        )

        blobs = []
        for lbl in range(1, num_labels):
            area = int(stats[lbl, cv2.CC_STAT_AREA])
            if area < self._min_area:
                continue

            blob_mask = labels == lbl
            if float(heat[blob_mask].max()) < self._conf_threshold:
                continue

            blobs.append((lbl, area))

        blobs.sort(key=lambda x: x[1], reverse=True)
        return blobs, stats
