import depthai as dai
from depthai_nodes import PRIMARY_COLOR, SECONDARY_COLOR, TRANSPARENT_PRIMARY_COLOR
from depthai_nodes.utils import AnnotationHelper
from typing import List
import cv2


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
                outline_color=PRIMARY_COLOR,
                fill_color=TRANSPARENT_PRIMARY_COLOR,
                thickness=2.0,
            )

            annotation_helper.draw_text(
                text=f"{self.labels[detection.label]} {int(detection.confidence * 100)}% \nx: {detection.spatialCoordinates.x:.2f}mm \ny: {detection.spatialCoordinates.y:.2f}mm \nz:{detection.spatialCoordinates.z:.2f}mm",
                position=(xmin + 0.01, ymin + 0.2),
                size=12,
                color=SECONDARY_COLOR,
            )

        annotations = annotation_helper.build(
            timestamp=detections_message.getTimestamp(),
            sequence_num=detections_message.getSequenceNum(),
        )

        depth_map = depth_message.getCvFrame()
        depth_map = cv2.applyColorMap(
            cv2.convertScaleAbs(depth_map, alpha=0.3), cv2.COLORMAP_JET
        )

        depth_frame = dai.ImgFrame()
        depth_frame.setCvFrame(depth_map, dai.ImgFrame.Type.BGR888i)
        depth_frame.setTimestamp(depth_message.getTimestamp())
        depth_frame.setSequenceNum(depth_message.getSequenceNum())

        self.out_annotations.send(annotations)
        self.out_depth.send(depth_frame)
