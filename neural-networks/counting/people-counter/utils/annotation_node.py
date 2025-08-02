import depthai as dai
from depthai_nodes import ImgDetectionsExtended
from depthai_nodes.utils import AnnotationHelper


class AnnotationNode(dai.node.HostNode):
    def __init__(self) -> None:
        """A host node that receives ImgDetections(Extended) message, counts detections, and
        outputs dai.ImgAnnotations message with the text annotation.
        """
        super().__init__()

    def build(self, det_msg: dai.Node.Output) -> "AnnotationNode":
        self.link_args(det_msg)
        return self

    def process(self, det_msg: dai.Buffer) -> None:
        assert isinstance(det_msg, (dai.ImgDetections, ImgDetectionsExtended))

        count = len(det_msg.detections)

        annotations = AnnotationHelper()

        annotations.draw_text(
            text=f"Count: {count}",
            position=(0.1, 0.1),  # top left corner
            background_color=(0, 0, 0, 1),  # black
        )

        annotations_msg = annotations.build(
            timestamp=det_msg.getTimestamp(),
            sequence_num=det_msg.getSequenceNum(),
        )

        self.out.send(annotations_msg)
