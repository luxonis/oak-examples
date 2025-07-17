from pathlib import Path
import cv2
import depthai as dai
import numpy as np
from depthai_nodes.utils import AnnotationHelper
from typing import List

from .texts import TextHelper, TitleHelper

JET_CUSTOM = cv2.applyColorMap(np.arange(256, dtype=np.uint8), cv2.COLORMAP_JET)
JET_CUSTOM = JET_CUSTOM[::-1]
JET_CUSTOM[0] = [0, 0, 0]

logo_path = Path(__file__).parent.parent / "assets" / "logo.jpeg"

LOGO = cv2.imread(str(logo_path))
LOGO = cv2.resize(LOGO, (250, 67))


class CombineOutputs(dai.node.HostNode):
    def __init__(self) -> None:
        super().__init__()
        self.output = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.ImgFrame, True)
            ]
        )
        self.detections_output = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.ImgAnnotations, True)
            ]
        )
        self.text = TextHelper()
        self.title = TitleHelper()
        self.label_map = None

    def build(
        self,
        color: dai.Node.Output,
        depth: dai.Node.Output,
        birdseye: dai.Node.Output,
        detections: dai.Node.Output,
        label_map: List[str],
    ) -> "CombineOutputs":
        self.link_args(color, depth, birdseye, detections)
        self.label_map = label_map
        return self

    def process(
        self,
        color_frame: dai.Buffer,
        depth_frame: dai.Buffer,
        bird_frame: dai.ImgFrame,
        spatial_dets: dai.Buffer,
    ) -> None:
        assert isinstance(color_frame, dai.ImgFrame)
        assert isinstance(depth_frame, dai.ImgFrame)
        assert isinstance(spatial_dets, dai.SpatialImgDetections)

        combined_frame = color_frame.getCvFrame()
        depth = depth_frame.getCvFrame()
        bird_view = bird_frame.getCvFrame()
        detections = spatial_dets.detections

        depth = cv2.normalize(depth, None, 256, 0, cv2.NORM_INF, cv2.CV_8UC3)
        depth = cv2.equalizeHist(depth)
        depth = cv2.applyColorMap(depth, JET_CUSTOM)
        half_frame = depth.shape[1] // 2
        combined_frame[:, half_frame:] = depth[:, half_frame:]

        height = combined_frame.shape[0]
        width = combined_frame.shape[1]
        combined_frame = cv2.flip(combined_frame, 1)

        resized_frame = cv2.resize(combined_frame, (1920, 1080))
        height, width = resized_frame.shape[:2]

        annotation_helper = AnnotationHelper()
        for detection in detections:
            # Use normalized coordinates adjusted for the flipped image
            left = 1 - detection.xmax  # After flip, xmax is the left edge
            right = 1 - detection.xmin  # After flip, xmin is the right edge
            top = detection.ymin
            bottom = detection.ymax
            # Draw bounding box (green outline)
            annotation_helper.draw_rectangle(
                (left, top),
                (right, bottom),
                outline_color=(0, 255, 0, 255),  # RGBA: green, fully opaque
                thickness=2,
            )
            try:
                label = self.label_map[detection.label]
            except KeyError:
                label = str(detection.label)
            text_x = left + 0.01  # Small offset in normalized units
            text_y = top + 0.02
            annotation_helper.draw_text(
                f"{label} {detection.confidence:.2f}",
                (text_x, text_y),
                color=(255, 255, 255, 255),  # White text
                size=32,
            )

        self.title.putText(resized_frame, "DEPTH", (30, 50))
        self.title.putText(resized_frame, "RGB", (width // 2 + 30, 50))

        # Add Luxonis logo
        cv2.rectangle(
            resized_frame,
            (width // 2 - 140, height - 90),
            (width // 2 + 140, height - 10),
            (255, 255, 255),
            -1,
        )
        resized_frame[
            (height - 82) : (height - 15), (width // 2 - 125) : (width // 2 + 125)
        ] = LOGO

        # Birdseye view
        cv2.rectangle(resized_frame, (10, 390), (110, 690), (255, 255, 255), 3)
        resized_frame[390:690, 10:110] = bird_view

        output_frame = dai.ImgFrame()
        output_frame.setCvFrame(
            resized_frame, dai.ImgFrame.Type.BGR888i
        )  # TODO: first resize then add birdframe and logo

        annotations_msg = annotation_helper.build(
            timestamp=output_frame.getTimestamp(),
            sequence_num=output_frame.getSequenceNum(),
        )
        self.detections_output.send(annotations_msg)
        self.output.send(output_frame)
