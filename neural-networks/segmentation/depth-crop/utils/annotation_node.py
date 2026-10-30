import cv2
import depthai as dai
import numpy as np
from depthai_nodes import PRIMARY_COLOR
from depthai_nodes.node.utils.message_remapping import remap_message


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
        mask = remap_message(
            mask, mask.getTransformation(), preview.getTransformation()
        )

        mask_data = mask.getCvMask()
        depth_frame = depth.getCvFrame()
        if mask_data.shape != frame.shape[:2] or depth_frame.shape != frame.shape:
            raise ValueError(
                "Mask, aligned depth and preview must share pixel geometry"
            )

        mask = np.zeros_like(frame)
        color = [
            int(PRIMARY_COLOR.b * 255),
            int(PRIMARY_COLOR.g * 255),
            int(PRIMARY_COLOR.r * 255),
        ]
        mask[mask_data == self.person_class] = color

        mask_overlay = cv2.addWeighted(frame, 1, mask, 0.5, 0)

        # cut out the mask from the depth frame
        mask_data = np.where(mask_data == self.person_class, 1, 0).astype(np.uint8)
        cutout_frame = depth_frame * mask_data[:, :, np.newaxis]

        mask_overlay_msg = dai.ImgFrame()
        mask_overlay_msg.setCvFrame(mask_overlay, dai.ImgFrame.Type.NV12)

        cutout_msg = dai.ImgFrame()
        cutout_msg.setCvFrame(cutout_frame, dai.ImgFrame.Type.NV12)

        depth_msg = dai.ImgFrame()
        depth_msg.setCvFrame(depth_frame, dai.ImgFrame.Type.NV12)
        for message in (mask_overlay_msg, cutout_msg, depth_msg):
            message.setBufferMetadataFrom(preview)
            message.setTransformation(preview.getTransformation())

        self.output_segmentation.send(mask_overlay_msg)
        self.output_cutout.send(cutout_msg)
        self.output_depth.send(depth_msg)
