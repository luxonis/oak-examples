import cv2
import depthai as dai
import numpy as np
from depthai_nodes import PRIMARY_COLOR


class AnnotationNode(dai.node.HostNode):
    def __init__(self) -> None:
        super().__init__()
        self.output_segmentation = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.ImgFrame, True)
            ]
        )
        self.output_cutout = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.ImgFrame, True)
            ]
        )
        self.output_depth = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.ImgFrame, True)
            ]
        )

        self.person_class = 15

    def build(
        self,
        preview: dai.Node.Output,
        depth: dai.Node.Output,
        mask: dai.Node.Output,
    ) -> "AnnotationNode":
        self.link_args(preview, depth, mask)
        return self

    def process(
        self, preview: dai.ImgFrame, depth: dai.ImgFrame, mask: dai.Buffer
    ) -> None:
        frame = preview.getCvFrame()

        assert isinstance(mask, dai.SegmentationMask)

        mask_data = mask.getCvMask()
        mask_data = cv2.resize(
            mask_data,
            (frame.shape[1], frame.shape[0]),
            interpolation=cv2.INTER_NEAREST,
        )

        mask = np.zeros_like(frame)
        color = [
            int(PRIMARY_COLOR.b * 255),
            int(PRIMARY_COLOR.g * 255),
            int(PRIMARY_COLOR.r * 255),
        ]
        mask[mask_data == self.person_class] = color

        mask_overlay = cv2.addWeighted(frame, 1, mask, 0.5, 0)

        depth_frame = colorize_depth(depth.getFrame())
        depth_frame = cv2.resize(depth_frame, (frame.shape[1], frame.shape[0]))

        # cut out the mask from the depth frame
        mask_data = np.where(mask_data == self.person_class, 1, 0).astype(np.uint8)
        cutout_frame = depth_frame * mask_data[:, :, np.newaxis]

        mask_overlay_msg = dai.ImgFrame()
        mask_overlay_msg.setCvFrame(mask_overlay, dai.ImgFrame.Type.NV12)
        mask_overlay_msg.setTimestamp(preview.getTimestamp())

        cutout_msg = dai.ImgFrame()
        cutout_msg.setCvFrame(cutout_frame, dai.ImgFrame.Type.NV12)
        cutout_msg.setTimestamp(preview.getTimestamp())

        depth_msg = dai.ImgFrame()
        depth_msg.setCvFrame(depth_frame, dai.ImgFrame.Type.NV12)
        depth_msg.setTimestamp(preview.getTimestamp())

        self.output_segmentation.send(mask_overlay_msg)
        self.output_cutout.send(cutout_msg)
        self.output_depth.send(depth_msg)


def colorize_depth(frame_depth: np.ndarray) -> np.ndarray:
    invalid_mask = frame_depth == 0
    valid_depth = frame_depth[~invalid_mask]
    if valid_depth.size == 0:
        return np.zeros((*frame_depth.shape, 3), dtype=np.uint8)

    min_depth = np.percentile(valid_depth, 3)
    max_depth = np.percentile(valid_depth, 95)
    if min_depth <= 0 or max_depth <= min_depth:
        return np.zeros((*frame_depth.shape, 3), dtype=np.uint8)

    log_min_depth = np.log(min_depth)
    log_max_depth = np.log(max_depth)
    log_depth = np.full(frame_depth.shape, log_min_depth, dtype=np.float32)
    np.log(frame_depth, out=log_depth, where=~invalid_mask)
    np.nan_to_num(log_depth, copy=False, nan=log_min_depth)
    log_depth = np.clip(log_depth, log_min_depth, log_max_depth)

    depth_frame = np.interp(log_depth, (log_min_depth, log_max_depth), (0, 255))
    depth_frame = np.nan_to_num(depth_frame).astype(np.uint8)
    depth_color = cv2.applyColorMap(depth_frame, cv2.COLORMAP_JET)
    depth_color[invalid_mask] = 0
    return depth_color
