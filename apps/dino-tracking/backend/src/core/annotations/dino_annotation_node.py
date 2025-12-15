import cv2
import numpy as np
import depthai as dai
from depthai_nodes.node.base_host_node import BaseHostNode


class DinoAnnotationNode(BaseHostNode):
    """
    Draw-only annotation node.

    Modes:
    - heatmap: translucent heatmap overlay
    - bbox: bounding boxes + IDs from Tracklets
    """

    def __init__(self, mode: str = "heatmap"):
        super().__init__()
        self.mode = mode

    def build(
        self,
        frame_msg: dai.Node.Output,
        heatmap_in: dai.Node.Output,
        tracklets_in: dai.Node.Output,
    ):
        self.link_args(frame_msg, heatmap_in, tracklets_in)
        return self

    def set_mode(self, mode: str):
        if mode in ["heatmap", "bbox"]:
            self.mode = mode
            self._logger.info(f"DinoAnnotationNode mode set to '{mode}'")

    def get_mode(self) -> str:
        return self.mode

    def process(
        self,
        frame_msg: dai.Buffer,
        heatmap: dai.Buffer,
        tracklets: dai.Buffer,
    ):
        frame = frame_msg.getCvFrame()

        if self.mode == "heatmap":
            self._draw_heatmap(frame, heatmap, frame_msg)
            return

        if self.mode == "bbox":
            self._draw_bboxes(frame, tracklets, frame_msg)
            return

    def _draw_heatmap(
        self,
        frame: np.ndarray,
        heatmap: dai.ImgFrame,
        ref_msg: dai.ImgFrame,
    ):
        mask = heatmap.getCvFrame()
        mask_gray = mask[..., 0] if mask.ndim == 3 else mask

        if mask_gray.shape[:2] != frame.shape[:2]:
            mask_gray = cv2.resize(
                mask_gray,
                (frame.shape[1], frame.shape[0]),
                interpolation=cv2.INTER_NEAREST,
            )

        heat = mask_gray.astype(np.float32) / 255.0

        heat_color = np.zeros_like(frame, dtype=np.uint8)
        heat_color[..., 1] = mask_gray

        alpha = (heat * 0.6)[..., None]
        result = (frame * (1 - alpha) + heat_color * alpha).astype(np.uint8)

        self._send(result, ref_msg)

    def _draw_bboxes(
        self, frame: dai.ImgFrame, tracklets: dai.Tracklets, ref_msg: dai.ImgFrame
    ):
        H, W = frame.shape[:2]

        for t in tracklets.tracklets:
            if t.status != dai.Tracklet.TrackingStatus.TRACKED:
                continue

            roi = t.roi.denormalize(W, H)
            x1 = int(roi.topLeft().x)
            y1 = int(roi.topLeft().y)
            x2 = int(roi.bottomRight().x)
            y2 = int(roi.bottomRight().y)

            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(
                frame,
                f"ID {t.id}",
                (x1, y1 - 6),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                2,
            )

        self._send(frame, ref_msg)

    def _send(self, frame: np.ndarray, ref_msg: dai.ImgFrame):
        out = dai.ImgFrame()
        out.setCvFrame(frame, self._img_frame_type)
        out.setSequenceNum(ref_msg.getSequenceNum())
        out.setTimestamp(ref_msg.getTimestamp())
        out.setTimestampDevice(ref_msg.getTimestampDevice())
        self.out.send(out)
