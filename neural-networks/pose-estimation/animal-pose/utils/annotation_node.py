import depthai as dai
from depthai_nodes import (
    ImgDetectionsExtended,
    ImgDetectionExtended,
    Keypoints,
    GatheredData,
    PRIMARY_COLOR,
    SECONDARY_COLOR,
)
from depthai_nodes.utils import AnnotationHelper
from typing import List


class AnnotationNode(dai.node.HostNode):
    def __init__(self) -> None:
        super().__init__()
        self.input_keypoints = self.createInput()
        self.out_detections = self.createOutput()
        self.out_pose_annotations = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.ImgAnnotations, True)
            ]
        )
        self.connection_pairs = [[]]
        self.padding = 0.1

    def build(
        self,
        input_detections: dai.Node.Output,
        connection_pairs: List[List[int]],
        padding: float,
    ) -> "AnnotationNode":
        self.connection_pairs = connection_pairs
        self.padding = padding
        self.link_args(input_detections)
        return self

    def process(self, gathered_data: dai.Buffer) -> None:
        assert isinstance(gathered_data, GatheredData)

        detections_message: ImgDetectionsExtended = gathered_data.reference_data

        detections_list: List[ImgDetectionExtended] = detections_message.detections

        annotation_helper = AnnotationHelper()

        padding = self.padding

        for ix, detection in enumerate(detections_list):
            detection.label_name = (
                "Animal"  # Because dai.ImgDetection does not have label_name
            )

            keypoints_message: Keypoints = gathered_data.gathered[ix]
            xmin, ymin, xmax, ymax = detection.rotated_rect.getOuterRect()

            slope_x = (xmax + padding) - (xmin - padding)
            slope_y = (ymax + padding) - (ymin - padding)
            xs = []
            ys = []
            for kp in keypoints_message.keypoints:
                x = min(max(xmin - padding + slope_x * kp.x, 0.0), 1.0)
                y = min(max(ymin - padding + slope_y * kp.y, 0.0), 1.0)
                xs.append(x)
                ys.append(y)

            kpts_to_draw = set()

            for connection in self.connection_pairs:
                pt1_idx, pt2_idx = connection
                if pt1_idx < len(xs) and pt2_idx < len(xs):
                    x1, y1 = xs[pt1_idx], ys[pt1_idx]
                    x2, y2 = xs[pt2_idx], ys[pt2_idx]
                    kpts_to_draw.add(pt1_idx)
                    kpts_to_draw.add(pt2_idx)
                    annotation_helper.draw_line(
                        pt1=(x1, y1),
                        pt2=(x2, y2),
                        color=SECONDARY_COLOR,
                        thickness=1.0,
                    )

            kpts_to_draw = [(xs[i], ys[i]) for i in kpts_to_draw]
            annotation_helper.draw_points(
                points=kpts_to_draw,
                color=PRIMARY_COLOR,
                thickness=2.0,
            )

        annotations = annotation_helper.build(
            timestamp=detections_message.getTimestamp(),
            sequence_num=detections_message.getSequenceNum(),
        )

        self.out_detections.send(detections_message)
        self.out_pose_annotations.send(annotations)
