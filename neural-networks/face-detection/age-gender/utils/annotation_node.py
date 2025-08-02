from typing import List
import depthai as dai

from depthai_nodes import (
    ImgDetectionsExtended,
    Predictions,
    Classifications,
    SECONDARY_COLOR,
)
from depthai_nodes.utils import AnnotationHelper


class AnnotationNode(dai.node.HostNode):
    def __init__(self) -> None:
        super().__init__()

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

        age_gender_msg_group_list: List[dai.MessageGroup] = gather_data_msg.gathered
        assert isinstance(age_gender_msg_group_list, list)
        assert all(
            isinstance(msg, dai.MessageGroup) for msg in age_gender_msg_group_list
        )

        assert len(img_detections_extended_msg.detections) == len(
            age_gender_msg_group_list
        )

        annotations = AnnotationHelper()

        for img_detection_extended_msg, age_gender_msg_group in zip(
            img_detections_extended_msg.detections, age_gender_msg_group_list
        ):
            age_msg: Predictions = age_gender_msg_group["0"]
            assert isinstance(age_msg, Predictions)
            gender_msg: Classifications = age_gender_msg_group["1"]
            assert isinstance(gender_msg, Classifications)

            xmin, ymin, xmax, ymax = (
                img_detection_extended_msg.rotated_rect.getOuterRect()
            )

            annotations.draw_rectangle(
                (xmin, ymin),
                (xmax, ymax),
            )

            annotations.draw_text(
                text=f"{gender_msg.classes[0][0]}; {int(age_msg.prediction * 100)}",
                position=(xmin + 0.005, ymin + 0.025),
                size=20,
                color=SECONDARY_COLOR,
            )

        annotations_msg = annotations.build(
            timestamp=img_detections_extended_msg.getTimestamp(),
            sequence_num=img_detections_extended_msg.getSequenceNum(),
        )

        self.out.send(annotations_msg)
