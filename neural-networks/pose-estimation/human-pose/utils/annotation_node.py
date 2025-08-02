from typing import List, Optional
import depthai as dai
from depthai_nodes import Keypoints
from depthai_nodes.utils import AnnotationHelper


class AnnotationNode(dai.node.HostNode):
    def __init__(self) -> None:
        super().__init__()
        self.out_pose_annotations = self.createOutput()
        self.connection_pairs = [[]]
        self.valid_labels = [0]
        self.padding = 0.1
        self.keypoint_conf_threshold = 0.5

    def build(
        self,
        gather_data_msg: dai.Node.Output,
        connection_pairs: List[List[int]],
        valid_labels: List[int],
        padding: Optional[float] = None,
        keypoint_conf_threshold: Optional[float] = None,
    ) -> "AnnotationNode":
        self.connection_pairs = connection_pairs
        self.valid_labels = valid_labels
        if padding:
            self.padding = padding
        if keypoint_conf_threshold:
            self.keypoint_conf_threshold = keypoint_conf_threshold
        self.link_args(gather_data_msg)
        return self

    def process(self, gather_data_msg: dai.Buffer) -> None:
        img_detections_msg: dai.ImgDetections = gather_data_msg.reference_data
        assert isinstance(img_detections_msg, dai.ImgDetections)

        keypoints_msg_list: List[Keypoints] = gather_data_msg.gathered
        assert isinstance(keypoints_msg_list, list)
        assert all(isinstance(msg, Keypoints) for msg in keypoints_msg_list)

        annotations = AnnotationHelper()

        for img_detection_msg, keypoints_msg in zip(
            img_detections_msg.detections, keypoints_msg_list
        ):
            xmin, ymin, xmax, ymax = (
                img_detection_msg.xmin,
                img_detection_msg.ymin,
                img_detection_msg.xmax,
                img_detection_msg.ymax,
            )

            slope_x = (xmax + self.padding) - (xmin - self.padding)
            slope_y = (ymax + self.padding) - (ymin - self.padding)
            xs = []
            ys = []
            confidences = []
            for keypoint_msg in keypoints_msg.keypoints:
                x = min(
                    max(xmin - self.padding + slope_x * keypoint_msg.x, 0.0),
                    1.0,
                )
                y = min(
                    max(ymin - self.padding + slope_y * keypoint_msg.y, 0.0),
                    1.0,
                )
                xs.append(x)
                ys.append(y)
                confidences.append(keypoint_msg.confidence)

            for connection in self.connection_pairs:
                pt1_idx, pt2_idx = connection
                if (
                    confidences[pt1_idx] < self.keypoint_conf_threshold
                    or confidences[pt2_idx] < self.keypoint_conf_threshold
                ):
                    continue
                if pt1_idx < len(xs) and pt2_idx < len(xs):
                    x1, y1 = xs[pt1_idx], ys[pt1_idx]
                    x2, y2 = xs[pt2_idx], ys[pt2_idx]

                    annotations.draw_line([x1, y1], [x2, y2], thickness=1)
                    annotations.draw_circle(center=[x1, y1], radius=0.005)
                    annotations.draw_circle(center=[x2, y2], radius=0.005)

        img_annotations_msg = annotations.build(
            timestamp=img_detections_msg.getTimestamp(),
            sequence_num=img_detections_msg.getSequenceNum(),
        )

        self.out_pose_annotations.send(img_annotations_msg)
