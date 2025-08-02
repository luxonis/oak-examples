import depthai as dai
from .measure_object_distance import ObjectDistances
from depthai_nodes.utils import AnnotationHelper
from depthai_nodes import SECONDARY_COLOR


class VisualizeObjectDistances(dai.node.HostNode):
    def __init__(self) -> None:
        super().__init__()

        self.output = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.ImgFrame, True)
            ]
        )

    def build(self, distances: dai.Node.Output) -> "VisualizeObjectDistances":
        self.link_args(distances)
        return self

    def process(self, distances: dai.Buffer):
        assert isinstance(distances, ObjectDistances)
        annotations = self._draw_overlay(distances)

        self.output.send(annotations)

    def _draw_overlay(self, distances: ObjectDistances):
        annotation_helper = AnnotationHelper()
        for distance in distances.distances:
            det1 = distance.detection1
            det2 = distance.detection2
            if not (det1.label == 80 and det2.label in [39, 41]) and not (
                det2.label == 80 and det1.label in [39, 41]
            ):
                continue

            x_start = (det1.xmin + det1.xmax) / 2
            y_start = (det1.ymin + det1.ymax) / 2
            x_end = (det2.xmin + det2.xmax) / 2
            y_end = (det2.ymin + det2.ymax) / 2

            annotation_helper.draw_line(
                pt1=(x_start, y_start),
                pt2=(x_end, y_end),
                thickness=2,
            )

            text = f"{round(distance.distance / 1000, 1)} m"
            label_x = (x_start + x_end) / 2
            label_y = (y_start + y_end) / 2 - 0.02
            annotation_helper.draw_text(
                text=text,
                position=(label_x, label_y),
                color=SECONDARY_COLOR,
                size=24,
            )

        img_annotations = annotation_helper.build(
            timestamp=distances.getTimestamp(),
            sequence_num=distances.getSequenceNum(),
        )

        return img_annotations
