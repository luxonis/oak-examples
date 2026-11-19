import depthai as dai
from depthai_nodes import PRIMARY_COLOR, SECONDARY_COLOR
from depthai_nodes.utils import AnnotationHelper

from .measure_object_distance import ObjectDistances


class DistanceAnnotations(dai.node.HostNode):
    """Draw the 3D distance between each pair of detected people."""

    def __init__(self) -> None:
        super().__init__()
        self.output = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.ImgAnnotations, True)
            ]
        )

    def build(self, distances: dai.Node.Output) -> "DistanceAnnotations":
        self.link_args(distances)
        return self

    def process(self, distances: dai.Buffer) -> None:
        assert isinstance(distances, ObjectDistances)
        annotations = AnnotationHelper()
        for pair in distances.distances:
            first = pair.detection1
            second = pair.detection2
            start = ((first.xmin + first.xmax) / 2, (first.ymin + first.ymax) / 2)
            end = ((second.xmin + second.xmax) / 2, (second.ymin + second.ymax) / 2)
            annotations.draw_line(
                pt1=start,
                pt2=end,
                color=PRIMARY_COLOR,
                thickness=2,
            )
            annotations.draw_text(
                text=f"{pair.distance / 1000:.1f} m",
                position=((start[0] + end[0]) / 2, (start[1] + end[1]) / 2 - 0.02),
                color=SECONDARY_COLOR,
                size=24,
            )

        self.output.send(
            annotations.build(
                timestamp=distances.getTimestamp(),
                sequence_num=distances.getSequenceNum(),
            )
        )
