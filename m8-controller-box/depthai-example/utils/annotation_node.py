import depthai as dai
from depthai_nodes import (
    ImgDetectionsExtended,
    ImgDetectionExtended,
    Keypoints,
    Predictions,
    GatheredData,
    SECONDARY_COLOR,
)
from depthai_nodes.utils import AnnotationHelper
from typing import List
from utils.gesture_recognition import recognize_gesture


class AnnotationNode(dai.node.HostNode):
    def __init__(self) -> None:
        super().__init__()
        self.gathered_data = self.createInput()
        self.out_detections = self.createOutput()
        self.out_pose_annotations = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.ImgAnnotations, True)
            ]
        )
        self.confidence_threshold = 0.5
        self.padding_factor = 0.1
        self.connection_pairs = [[]]

    def build(
        self,
        gathered_data: dai.Node.Output,
        video: dai.Node.Output,
        confidence_threshold: float,
        padding_factor: float,
        connections_pairs: List[List[int]],
    ) -> "AnnotationNode":
        self.confidence_threshold = confidence_threshold
        self.padding_factor = padding_factor
        self.connection_pairs = connections_pairs
        self.link_args(gathered_data, video)
        return self

    def process(self, gathered_data: dai.Buffer, video_message: dai.ImgFrame) -> None:
        assert isinstance(gathered_data, GatheredData)

        detections_message: ImgDetectionsExtended = gathered_data.reference_data
        detections_list: List[ImgDetectionExtended] = detections_message.detections

        new_dets = ImgDetectionsExtended()
        new_dets.transformation = video_message.getTransformation()

        annotation_helper = AnnotationHelper()

        for ix, detection in enumerate(detections_list):
            keypoints_msg: Keypoints = gathered_data.gathered[ix]["0"]
            confidence_msg: Predictions = gathered_data.gathered[ix]["1"]
            handness_msg: Predictions = gathered_data.gathered[ix]["2"]

            hand_confidence = confidence_msg.prediction
            handness = handness_msg.prediction

            if hand_confidence < self.confidence_threshold:
                continue

            width = detection.rotated_rect.size.width
            height = detection.rotated_rect.size.height

            xmin = detection.rotated_rect.center.x - width / 2
            xmax = detection.rotated_rect.center.x + width / 2
            ymin = detection.rotated_rect.center.y - height / 2
            ymax = detection.rotated_rect.center.y + height / 2

            padding = self.padding_factor

            slope_x = (xmax + padding) - (xmin - padding)
            slope_y = (ymax + padding) - (ymin - padding)

            new_det = ImgDetectionExtended()
            new_det.rotated_rect = (
                detection.rotated_rect.center.x,
                detection.rotated_rect.center.y,
                detection.rotated_rect.size.width + 2 * padding,
                detection.rotated_rect.size.height + 2 * padding,
                detection.rotated_rect.angle,
            )
            new_det.label = 0
            new_det.label_name = "Hand"
            new_det.confidence = detection.confidence
            new_dets.detections.append(new_det)

            xs = []
            ys = []

            for kp in keypoints_msg.keypoints:
                x = min(max(xmin - padding + slope_x * kp.x, 0.0), 1.0)
                y = min(max(ymin - padding + slope_y * kp.y, 0.0), 1.0)
                xs.append(x)
                ys.append(y)

            for connection in self.connection_pairs:
                pt1_ix, pt2_ix = connection
                annotation_helper.draw_line(
                    pt1=(xs[pt1_ix], ys[pt1_ix]),
                    pt2=(xs[pt2_ix], ys[pt2_ix]),
                )

            keypoints = [[kpt[0], kpt[1]] for kpt in zip(xs, ys)]

            gesture = recognize_gesture(keypoints)

            text = "Left" if handness < 0.5 else "Right"
            text += f" {gesture}"

            text_x = detection.rotated_rect.center.x - 0.05
            text_y = detection.rotated_rect.center.y - height / 2 - 0.10

            annotation_helper.draw_text(
                text=text,
                position=(text_x, text_y),
                color=SECONDARY_COLOR,
                size=32,
            )

            annotation_helper.draw_points(
                points=keypoints, color=SECONDARY_COLOR, thickness=2
            )

        new_dets.setTimestamp(detections_message.getTimestamp())
        new_dets.setSequenceNum(detections_message.getSequenceNum())
        self.out_detections.send(new_dets)

        annotations = annotation_helper.build(
            timestamp=detections_message.getTimestamp(),
            sequence_num=detections_message.getSequenceNum(),
        )

        self.out_pose_annotations.send(annotations)
