from typing import List

import depthai as dai

from depthai_nodes import ImgDetectionsExtended, Classifications, SECONDARY_COLOR
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
        dets_msg: ImgDetectionsExtended = gather_data_msg.reference_data
        assert isinstance(dets_msg, ImgDetectionsExtended)

        rec_msg_list: List[Classifications] = gather_data_msg.gathered
        assert isinstance(rec_msg_list, list)
        assert all(isinstance(rec_msg, Classifications) for rec_msg in rec_msg_list)
        assert len(dets_msg.detections) == len(rec_msg_list)

        annotations = AnnotationHelper()

        for det_msg, rec_msg in zip(dets_msg.detections, rec_msg_list):
            xmin, ymin, xmax, ymax = det_msg.rotated_rect.getOuterRect()

            annotations.draw_rectangle(
                (xmin, ymin),
                (xmax, ymax),
            )

            annotations.draw_text(
                text=f"{rec_msg.top_class} ({rec_msg.top_score.item():.2f})",
                position=(xmin + 0.005, ymin + 0.025),
                size=20,
                color=SECONDARY_COLOR,
            )

        annotations_msg = annotations.build(
            timestamp=dets_msg.getTimestamp(),
            sequence_num=dets_msg.getSequenceNum(),
        )

        self.out.send(annotations_msg)
