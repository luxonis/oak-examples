# core/fusion/face_features_node.py
from typing import List
import depthai as dai

from messages.messages import FaceData, FaceFeaturesMessage
from .face_features_merger import merge_face_features


class FaceFeaturesNode(dai.node.HostNode):
    """
    Host node that aggregates all face-related NN outputs (age/gender, emotions, re-id, crops) into FaceData messages.
    """

    def __init__(self) -> None:
        super().__init__()
        self.in_age_gender = self.createInput()
        self.in_emotions = self.createInput()
        self.in_crops = self.createInput()
        self.in_reid = self.createInput()

    def build(
        self,
        age_gender: dai.Node.Output,
        emotions: dai.Node.Output,
        crops: dai.Node.Output,
        reid: dai.Node.Output,
    ) -> "FaceFeaturesNode":
        self.link_args(age_gender, emotions, crops, reid)
        return self

    def process(
        self,
        age_gender: dai.Buffer,
        emotions: dai.Buffer,
        crops: dai.Buffer,
        reid: dai.Buffer,
    ) -> None:
        faces: List[FaceData] = merge_face_features(
            age_gender=age_gender,
            emotions=emotions,
            crops=crops,
            reid=reid,
        )

        msg = FaceFeaturesMessage(faces)
        msg.setTimestamp(age_gender.getTimestamp())
        msg.setSequenceNum(age_gender.getSequenceNum())
        self.out.send(msg)
