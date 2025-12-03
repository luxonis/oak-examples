import depthai as dai
from depthai_nodes import PRIMARY_COLOR, SECONDARY_COLOR
from depthai_nodes.utils import AnnotationHelper
from typing import List
import cv2
import numpy as np

PURPLE_COLOR = (200 / 255.0, 0 / 255.0, 255 / 255.0, 1.0)
PURPLE_FILL_COLOR = (200 / 255.0, 0 / 255.0, 255 / 255.0, 0.15)


class AnnotationNode(dai.node.HostNode):
    def __init__(self) -> None:
        super().__init__()
        self.input_detections = self.createInput()
        self.out_annotations = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.ImgAnnotations, True)
            ]
        )
        self.out_depth = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.ImgFrame, True)
            ]
        )
        self.labels = []

    def build(
        self,
        input_detections: dai.Node.Output,
        depth: dai.Node.Output,
        labels: List[str],
    ) -> "AnnotationNode":
        self.labels = labels
        self.link_args(input_detections, depth)
        return self

    def process(
        self, detections_message: dai.Buffer, depth_message: dai.ImgFrame
    ) -> None:
        assert isinstance(detections_message, dai.SpatialImgDetections)

        detections_list: List[dai.SpatialImgDetection] = detections_message.detections

        annotation_helper = AnnotationHelper()

        for ix, detection in enumerate(detections_list):
            xmin, ymin, xmax, ymax = (
                detection.xmin,
                detection.ymin,
                detection.xmax,
                detection.ymax,
            )
            annotation_helper.draw_rectangle(
                top_left=(xmin, ymin),
                bottom_right=(xmax, ymax),
                outline_color=PURPLE_COLOR,
                fill_color=PURPLE_FILL_COLOR,
                thickness=2.0,
            )

            depth_mm = detection.spatialCoordinates.z
            depth_m = round(depth_mm / 1000.0, 1)
            label = self.labels[detection.label]
            combined_text = f"{label}: {depth_m}m"
            
            # Determine if text should be at top or bottom
            # If bounding box is too close to top (ymin < 0.08), put text at bottom
            if ymin > 0.08:
                # Enough space at top, place text directly above bounding box
                text_y = ymin
            else:
                # Not enough space at top, place text directly below bounding box
                text_y = ymax
            
            # Use purple background with transparency to match the bounding box
            text_bg_color = (200 / 255.0, 0 / 255.0, 255 / 255.0, 0.8)
            
            annotation_helper.draw_text(
                text=combined_text,
                position=(xmin, text_y),
                size=22,
                color=SECONDARY_COLOR,
                background_color=text_bg_color,
            )

        annotations = annotation_helper.build(
            timestamp=detections_message.getTimestamp(),
            sequence_num=detections_message.getSequenceNum(),
        )

        depth_map = depth_message.getCvFrame()
        
        valid_mask = depth_map > 0
        if np.any(valid_mask):
            valid_depths = depth_map[valid_mask]
            lower_percentile = np.percentile(valid_depths, 1.0)
            upper_percentile = np.percentile(valid_depths, 99.0)
            
            depth_clipped = np.clip(depth_map, lower_percentile, upper_percentile)
            depth_normalized = np.zeros_like(depth_map, dtype=np.uint8)
            
            if upper_percentile > lower_percentile:
                depth_normalized[valid_mask] = (
                    ((depth_clipped[valid_mask] - lower_percentile) / 
                     (upper_percentile - lower_percentile) * 255)
                ).astype(np.uint8)
            
            depth_map = cv2.applyColorMap(depth_normalized, cv2.COLORMAP_JET)
        else:
            depth_map = np.zeros((depth_map.shape[0], depth_map.shape[1], 3), dtype=np.uint8)

        depth_frame = dai.ImgFrame()
        depth_frame.setCvFrame(depth_map, dai.ImgFrame.Type.BGR888i)
        depth_frame.setTimestamp(depth_message.getTimestamp())
        depth_frame.setSequenceNum(depth_message.getSequenceNum())

        self.out_annotations.send(annotations)
        self.out_depth.send(depth_frame)
