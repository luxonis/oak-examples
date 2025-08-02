import depthai as dai
from depthai_nodes import ImgDetectionsExtended, SegmentationMask

import cv2
import numpy as np


class AnnotationNode(dai.node.HostNode):
    def __init__(
        self,
    ) -> None:
        super().__init__()
        self.out_segmentations = self.createOutput()
        self.out_detections = self.createOutput()

    def build(
        self,
        frame: dai.Node.Output,
        detections: dai.Node.Output,
        road_segmentations: dai.Node.Output,
        lane_segmentations: dai.Node.Output,
    ) -> "AnnotationNode":
        self.link_args(frame, detections, road_segmentations, lane_segmentations)
        return self

    def process(
        self,
        frame: dai.Buffer,
        detections_message: dai.Buffer,
        road_segmentations_message: dai.Buffer,
        lane_segmentations_message: dai.Buffer,
    ) -> None:
        assert isinstance(frame, dai.ImgFrame)
        assert isinstance(detections_message, ImgDetectionsExtended)
        assert isinstance(road_segmentations_message, SegmentationMask)
        assert isinstance(lane_segmentations_message, SegmentationMask)

        detections_message.setTransformation(frame.getTransformation())

        frame = frame.getCvFrame()
        output_frame = dai.ImgFrame()

        mask = road_segmentations_message.mask

        lane_segmentation_mask = lane_segmentations_message.mask > 0
        mask[lane_segmentation_mask] = 2

        unique_values = np.unique(mask[mask >= 0])
        scaled_mask = np.zeros_like(mask, dtype=np.uint8)

        if unique_values.size != 0:
            min_val, max_val = unique_values.min(), unique_values.max()

            if min_val == max_val:
                scaled_mask = np.ones_like(mask, dtype=np.uint8) * 255
            else:
                scaled_mask = ((mask - min_val) / (max_val - min_val) * 255).astype(
                    np.uint8
                )
            scaled_mask[mask == -1] = 0
        colored_mask = cv2.applyColorMap(scaled_mask, cv2.COLORMAP_RAINBOW)
        colored_mask[mask == 0] = [0, 0, 0]
        colored_mask[mask == -1] = [0, 0, 0]

        frame_height, frame_width, _ = frame.shape
        colored_mask = cv2.resize(
            colored_mask, (frame_width, frame_height), interpolation=cv2.INTER_AREA
        )

        colored_frame = cv2.addWeighted(frame, 0.8, colored_mask, 0.5, 0)

        output_frame.setTimestamp(detections_message.getTimestamp())
        output_frame.setSequenceNum(detections_message.getSequenceNum())

        self.out_detections.send(detections_message)

        self.out_segmentations.send(
            output_frame.setCvFrame(colored_frame, dai.ImgFrame.Type.BGR888i)
        )
