from typing import List
from collections import deque
import depthai as dai
from depthai_nodes.utils import AnnotationHelper
from depthai_nodes import ImgDetectionsExtended, Keypoints

from utils.face_landmarks import determine_fatigue


class AnnotationNode(dai.node.HostNode):
    def __init__(self) -> None:
        super().__init__()
        self._closed_eye_duration = deque(maxlen=30)
        self._head_tilted_duration = deque(maxlen=30)

    def build(self, gather_data_msg) -> "AnnotationNode":
        self.link_args(gather_data_msg)
        return self

    def process(self, gather_data_msg) -> None:
        detections_msg: ImgDetectionsExtended = gather_data_msg.reference_data
        assert isinstance(detections_msg, ImgDetectionsExtended)
        src_w, src_h = detections_msg.transformation.getSize()

        landmarks_msg_list: List[Keypoints] = gather_data_msg.gathered
        assert isinstance(landmarks_msg_list, list)
        assert all(isinstance(rec_msg, Keypoints) for rec_msg in landmarks_msg_list)
        assert len(landmarks_msg_list) == len(detections_msg.detections)

        annotations = AnnotationHelper()

        for detection, landmarks in zip(detections_msg.detections, landmarks_msg_list):
            pitch, eyes_closed = determine_fatigue((src_h, src_w), landmarks)

            self._head_tilted_duration.append(pitch)
            self._closed_eye_duration.append(eyes_closed)

            percent_closed_eyes = sum(self._closed_eye_duration) / len(
                self._closed_eye_duration
            )
            percent_tilted = sum(self._head_tilted_duration) / len(
                self._head_tilted_duration
            )

            if percent_tilted >= 0.75:
                annotations.draw_text(
                    text="Head Tilted!",
                    position=(0.1, 0.1),
                )

            if percent_closed_eyes >= 0.75:
                annotations.draw_text(
                    text="Eyes Closed!",
                    position=(0.1, 0.2),
                )

        annotations_msg = annotations.build(
            timestamp=detections_msg.getTimestamp(),
            sequence_num=detections_msg.getSequenceNum(),
        )

        self.out.send(annotations_msg)
