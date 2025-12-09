from typing import List
import depthai as dai

from depthai_nodes import ImgDetectionsExtended, SECONDARY_COLOR
from depthai_nodes.utils import AnnotationHelper


class AnnotationNode(dai.node.ThreadedHostNode):
    def __init__(self) -> None:
        super().__init__()

        self.input = self.createInput()
        self.input.setPossibleDatatypes([(dai.DatatypeEnum.Buffer, True)])

        self.out = self.createOutput()
        self.out.setPossibleDatatypes([(dai.DatatypeEnum.Buffer, True)])

    def build(
        self,
        gather_data_msg: dai.Node.Output,
    ) -> "AnnotationNode":
        gather_data_msg.link(self.input)
        return self

    def run(self) -> None:
        while self.isRunning():
            gather_data_msg: dai.Buffer = self.input.get()

            img_detections_extended_msg: ImgDetectionsExtended = (
                gather_data_msg.reference_data
            )

            msg_group_list: List[dai.MessageGroup] = gather_data_msg.gathered

            annotations = AnnotationHelper()

            for img_detection_extended_msg, msg_group in zip(
                img_detections_extended_msg.detections, msg_group_list
            ):
                xmin, ymin, xmax, ymax = (
                    img_detection_extended_msg.rotated_rect.getOuterRect()
                )

                try:
                    xmin = float(xmin)
                    ymin = float(ymin)
                    xmax = float(xmax)
                    ymax = float(ymax)
                except Exception:
                    pass

                xmin = max(0.0, min(1.0, xmin))
                ymin = max(0.0, min(1.0, ymin))
                xmax = max(0.0, min(1.0, xmax))
                ymax = max(0.0, min(1.0, ymax))

                annotations.draw_rectangle((xmin, ymin), (xmax, ymax))

                barcode_text = ""
                if "0" in msg_group:
                    buf_msg: dai.Buffer = msg_group["0"]
                    barcode_text = buf_msg.getData().decode("utf-8", errors="ignore")

                if barcode_text:
                    annotations.draw_text(
                        text=barcode_text,
                        position=(xmin + 0.01, ymin + 0.03),
                        size=20,
                        color=SECONDARY_COLOR,
                    )

            annotations_msg = annotations.build(
                timestamp=img_detections_extended_msg.getTimestamp(),
                sequence_num=img_detections_extended_msg.getSequenceNum(),
            )

            self.out.send(annotations_msg)
