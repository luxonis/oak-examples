from typing import List
import numpy as np
import depthai as dai

from depthai_nodes import ImgDetectionsExtended, Predictions
from depthai_nodes.utils import AnnotationHelper


class AnnotationNode(dai.node.HostNode):
    def __init__(self) -> None:
        super().__init__()
        self._min_threshold = 15

    def build(
        self,
        gather_data_msg: dai.Node.Output,
    ) -> "AnnotationNode":
        self.link_args(gather_data_msg)
        return self

    def process(self, gather_data_msg: dai.Buffer) -> None:
        img_detections_extended_msg: ImgDetectionsExtended = (
            gather_data_msg.reference_data
        )
        assert isinstance(img_detections_extended_msg, ImgDetectionsExtended)

        pose_msg_group_list: List[dai.MessageGroup] = gather_data_msg.gathered
        assert isinstance(pose_msg_group_list, list)
        assert all(isinstance(msg, dai.MessageGroup) for msg in pose_msg_group_list)

        assert len(img_detections_extended_msg.detections) == len(pose_msg_group_list)

        annotations = AnnotationHelper()

        for img_detection_extended_msg, pose_msg_group in zip(
            img_detections_extended_msg.detections, pose_msg_group_list
        ):
            yaw_msg: Predictions = pose_msg_group["0"]
            assert isinstance(yaw_msg, Predictions)
            yaw = yaw_msg.prediction
            roll_msg: Predictions = pose_msg_group["1"]
            assert isinstance(roll_msg, Predictions)
            roll = roll_msg.prediction
            pitch_msg: Predictions = pose_msg_group["2"]
            assert isinstance(pitch_msg, Predictions)
            pitch = pitch_msg.prediction

            pose_text = self._decode_pose(yaw, pitch, roll)

            pose_information = f"Pitch: {pitch:.0f} \nYaw: {yaw:.0f} \nRoll: {roll:.0f}"

            outer_points = img_detection_extended_msg.rotated_rect.getOuterRect()
            x_min, y_min, x_max, _ = [np.round(x, 2) for x in outer_points]

            annotations.draw_text(pose_information, (x_max, y_min + 0.1), size=16)
            annotations.draw_text(pose_text, (x_min, y_min), size=28)

        annotations_msg = annotations.build(
            timestamp=img_detections_extended_msg.getTimestamp(),
            sequence_num=img_detections_extended_msg.getSequenceNum(),
        )

        self.out.send(annotations_msg)

    def _decode_pose(self, yaw: float, pitch: float, roll: float) -> str:
        vals = np.array([abs(pitch), abs(yaw), abs(roll)])
        max_index = np.argmax(vals)

        if vals[max_index] < self._min_threshold:
            return ""

        if max_index == 0:
            if pitch > 0:
                txt = "Look down"
            else:
                txt = "Look up"
        elif max_index == 1:
            if yaw > 0:
                txt = "Turn left"
            else:
                txt = "Turn right"
        elif max_index == 2:
            if roll > 0:
                txt = "Tilt left"
            else:
                txt = "Tilt right"

        return txt
