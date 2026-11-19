import depthai as dai
from depthai_nodes import GatheredData, SECONDARY_COLOR
from depthai.beta import Predictions, Keypoints
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
        confidence_threshold: float,
        padding_factor: float,
        connections_pairs: List[List[int]],
    ) -> "AnnotationNode":
        self.confidence_threshold = confidence_threshold
        self.padding_factor = padding_factor
        self.connection_pairs = connections_pairs
        self.link_args(gathered_data)
        return self

    def process(self, gathered_data: dai.Buffer) -> None:
        assert isinstance(gathered_data, GatheredData)

        detections_message: dai.ImgDetections = gathered_data.reference_data
        detections_list: List[dai.ImgDetection] = detections_message.detections
        detection_transformation = detections_message.getTransformation()
        detection_width, detection_height = detection_transformation.getSize()

        new_dets = dai.ImgDetections()
        new_dets.setTransformation(detection_transformation)

        annotation_helper = AnnotationHelper()
        det_list = []

        for ix, detection in enumerate(detections_list):
            keypoints_msg: Keypoints = gathered_data.items[ix]["0"]
            confidence_msg: Predictions = gathered_data.items[ix]["1"]
            handness_msg: Predictions = gathered_data.items[ix]["2"]

            hand_confidence = confidence_msg.getFirstPrediction()
            handness = handness_msg.getFirstPrediction()

            if hand_confidence < self.confidence_threshold:
                continue

            rotated_rect = detection.getBoundingBox()
            height = rotated_rect.size.height
            padding = self.padding_factor

            new_det = dai.ImgDetection()
            new_det.setBoundingBox(
                dai.RotatedRect(
                    rotated_rect.center,
                    dai.Size2f(
                        rotated_rect.size.width + 2 * padding,
                        rotated_rect.size.height + 2 * padding,
                    ),
                    rotated_rect.angle,
                )
            )
            new_det.label = 0
            new_det.labelName = "Hand"
            new_det.confidence = detection.confidence
            det_list.append(new_det)

            xs = []
            ys = []
            keypoints_in_crop = []
            crop_transformation = keypoints_msg.getTransformation()
            crop_width, crop_height = crop_transformation.getSize()

            for kp in keypoints_msg.getKeypoints():
                crop_x = kp.imageCoordinates.x
                crop_y = kp.imageCoordinates.y
                keypoints_in_crop.append((crop_x, crop_y))
                point_in_detection = crop_transformation.remapPointTo(
                    detection_transformation,
                    dai.Point2f(crop_x * crop_width, crop_y * crop_height),
                )
                x = min(max(point_in_detection.x / detection_width, 0.0), 1.0)
                y = min(max(point_in_detection.y / detection_height, 0.0), 1.0)
                xs.append(x)
                ys.append(y)

            for connection in self.connection_pairs:
                pt1_ix, pt2_ix = connection
                annotation_helper.draw_line(
                    pt1=(xs[pt1_ix], ys[pt1_ix]),
                    pt2=(xs[pt2_ix], ys[pt2_ix]),
                )

            keypoints = [[kpt[0], kpt[1]] for kpt in zip(xs, ys)]

            gesture = recognize_gesture(keypoints_in_crop)

            text = "Left" if handness < 0.5 else "Right"
            text += f" {gesture}"

            text_x = detection.getBoundingBox().center.x - 0.05
            text_y = detection.getBoundingBox().center.y - height / 2 - 0.10

            annotation_helper.draw_text(
                text=text,
                position=(text_x, text_y),
                color=SECONDARY_COLOR,
                size=32,
            )

            annotation_helper.draw_points(
                points=keypoints, color=SECONDARY_COLOR, thickness=2
            )

        new_dets.detections = det_list
        new_dets.setTimestamp(detections_message.getTimestamp())
        new_dets.setSequenceNum(detections_message.getSequenceNum())
        self.out_detections.send(new_dets)

        annotations = annotation_helper.build(
            timestamp=detections_message.getTimestamp(),
            sequence_num=detections_message.getSequenceNum(),
        )

        self.out_pose_annotations.send(annotations)
