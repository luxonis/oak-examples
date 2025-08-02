import depthai as dai
import numpy as np

from depthai_nodes import Map2D
from depthai_nodes.utils import AnnotationHelper


class AnnotationNode(dai.node.HostNode):
    """A host node that receives a crowd density map, calculates the number of people in the crowd,
    and outputs dai.ImgAnnotations message with the text annotation.
    """

    def __init__(self):
        super().__init__()

    def build(self, density_map_msg: dai.Node.Output):
        self.link_args(density_map_msg)
        return self

    def process(self, density_map_msg: dai.Buffer):
        assert isinstance(density_map_msg, Map2D)

        count = np.sum(density_map_msg.map)

        annotations = AnnotationHelper()

        annotations.draw_text(
            text=f"Count: {count:.2f}",
            position=(0.1, 0.1),  # top left corner
            background_color=(0, 0, 0, 1),  # black
        )

        annotations_msg = annotations.build(
            timestamp=density_map_msg.getTimestamp(),
            sequence_num=density_map_msg.getSequenceNum(),
        )

        self.out.send(annotations_msg)
