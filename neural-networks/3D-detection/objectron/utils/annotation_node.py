import depthai as dai
from depthai_nodes import (
    ImgDetectionsExtended,
    Keypoints,
    GatheredData,
    PRIMARY_COLOR,
    SECONDARY_COLOR,
)
from depthai_nodes.utils.annotation_helper import AnnotationHelper
from typing import List


class AnnotationNode(dai.node.HostNode):
    def __init__(
        self,
    ) -> None:
        super().__init__()

        self.out_detections = self.createOutput()
        self.out_pose_annotations = self.createOutput()

        self.connection_pairs = [[]]
        self.padding = 0.2

    def build(
        self,
        gathered_data: dai.Node.Output,
        connection_pairs: List[List[int]],
        padding: float,
    ) -> "AnnotationNode":
        self.connection_pairs = connection_pairs
        self.padding = padding
        self.link_args(gathered_data)
        return self

    def process(self, gathered_data: dai.Buffer) -> None:
        assert isinstance(gathered_data, GatheredData)

        detections_message: ImgDetectionsExtended = gathered_data.reference_data
        detections_list: List[dai.ImgDetection] = detections_message.detections

        annotation_helper = AnnotationHelper()

        padding = self.padding

        for ix, detection in enumerate(detections_list):
            keypoints_msg: Keypoints = gathered_data.gathered[ix]

            slope_x = (detection.xmax + padding) - (detection.xmin - padding)
            slope_y = (detection.ymax + padding) - (detection.ymin - padding)
            xs = []
            ys = []
            for kp in keypoints_msg.keypoints:
                x = min(max(detection.xmin - padding + slope_x * kp.x, 0.0), 1.0)
                y = min(max(detection.ymin - padding + slope_y * kp.y, 0.0), 1.0)
                xs.append(x)
                ys.append(y)

            annotation_helper.draw_points(
                points=[(x, y) for x, y in zip(xs, ys)],
                color=SECONDARY_COLOR,
                thickness=2.0,
            )

            for connection in self.connection_pairs:
                pt1_idx, pt2_idx = connection
                if pt1_idx < len(xs) and pt2_idx < len(ys):
                    x1, y1 = xs[pt1_idx], ys[pt1_idx]
                    x2, y2 = xs[pt2_idx], ys[pt2_idx]
                    annotation_helper.draw_line(
                        pt1=(x1, y1),
                        pt2=(x2, y2),
                        color=PRIMARY_COLOR,
                    )

            annotation_helper.draw_text(
                text=f"{(detection.confidence * 100):.2f}%",
                position=(detection.xmin, detection.ymin - 0.05),
                color=SECONDARY_COLOR,
                size=16.0,
            )

        annotations = annotation_helper.build(
            timestamp=detections_message.getTimestamp(),
            sequence_num=detections_message.getSequenceNum(),
        )
        self.out_pose_annotations.send(annotations)
