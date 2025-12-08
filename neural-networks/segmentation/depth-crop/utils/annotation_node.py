import cv2
import depthai as dai
import numpy as np
from depthai_nodes import SegmentationMask, PRIMARY_COLOR

# Custom colormap with 0 mapped to black - better disparity visualization
JET_CUSTOM = cv2.applyColorMap(np.arange(256, dtype=np.uint8), cv2.COLORMAP_JET)
JET_CUSTOM[0] = [0, 0, 0]


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
        disparity: dai.Node.Output,
        mask: dai.Node.Output,
        max_disparity: int,
    ) -> "AnnotationNode":
        self.link_args(preview, disparity, mask)

        self.disp_multiplier = 255 / max_disparity
        return self

    def process(
        self, preview: dai.ImgFrame, disparity: dai.ImgFrame, mask: dai.Buffer
    ) -> None:
        frame = preview.getCvFrame()

        assert isinstance(mask, SegmentationMask)

        mask_data = mask.mask
        mask_data = cv2.resize(mask_data, (frame.shape[1], frame.shape[0]))

        mask = np.zeros_like(frame)
        color = [
            int(PRIMARY_COLOR.b * 255),
            int(PRIMARY_COLOR.g * 255),
            int(PRIMARY_COLOR.r * 255),
        ]
        mask[mask_data == self.person_class] = color

        mask_overlay = cv2.addWeighted(frame, 1, mask, 0.5, 0)

        disp_frame = (disparity.getFrame() * self.disp_multiplier).astype(np.uint8)
        depth_frame = cv2.applyColorMap(disp_frame, JET_CUSTOM)
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
