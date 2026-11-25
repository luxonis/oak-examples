import depthai as dai
from depthai_nodes import PRIMARY_COLOR, SECONDARY_COLOR
from depthai_nodes.utils import AnnotationHelper

from .measure_object_distance import ObjectDistances


def render_annotations(distances: ObjectDistances) -> dai.ImgAnnotations:
    annotations = AnnotationHelper()
    for tracklet in distances.tracklets:
        roi = tracklet.roi
        annotations.draw_rectangle(
            top_left=(roi.x, roi.y),
            bottom_right=(roi.x + roi.width, roi.y + roi.height),
            outline_color=PRIMARY_COLOR,
            thickness=2,
        )
        annotations.draw_text(
            text=f"ID {tracklet.id}",
            position=(roi.x, roi.y),
            color=SECONDARY_COLOR,
            size=24,
        )
    for pair in distances.distances:
        first = pair.detection1
        second = pair.detection2
        start = (
            first.roi.x + first.roi.width / 2,
            first.roi.y + first.roi.height / 2,
        )
        end = (
            second.roi.x + second.roi.width / 2,
            second.roi.y + second.roi.height / 2,
        )
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

    return annotations.build(
        timestamp=distances.getTimestamp(),
        sequence_num=distances.getSequenceNum(),
    )


class DistanceAnnotations(dai.node.HostNode):
    """Draw track IDs and the 3D distance between detected people."""

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
        self.output.send(render_annotations(distances))
