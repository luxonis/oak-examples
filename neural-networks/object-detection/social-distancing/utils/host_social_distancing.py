import depthai as dai
from typing import List, Tuple
from .measure_object_distance import ObjectDistances, DetectionDistance
from depthai_nodes.utils import AnnotationHelper
from depthai_nodes import PRIMARY_COLOR, SECONDARY_COLOR

ALERT_THRESHOLD = 0.5
STATE_QUEUE_LENGTH = 15


class SocialDistancing(dai.node.HostNode):
    def __init__(self) -> None:
        super().__init__()

        self.output = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.ImgAnnotations, True)
            ]
        )

        self._state_queue = []

        self.alert_distance = 1500  # mm

    def build(
        self, distances: dai.Node.Output, alert_distance: float = 1500
    ) -> "SocialDistancing":
        self.alert_distance = alert_distance
        self.link_args(distances)
        return self

    def process(self, distances: dai.Buffer):
        assert isinstance(distances, ObjectDistances)

        close_detections = self._get_all_close_detections(distances)
        self._add_state(len(close_detections) > 0)

        annotations = self._create_annotations(distances)

        self.output.send(annotations)

    def _create_annotations(self, distances: ObjectDistances):
        annotation_helper = AnnotationHelper()

        if self._should_alert:
            self._add_alert_annotation(annotation_helper)

        for distance in distances.distances:
            self._add_distance_annotation(annotation_helper, distance)

        annotations = annotation_helper.build(
            timestamp=distances.getTimestamp(), sequence_num=distances.getSequenceNum()
        )

        return annotations

    def _add_alert_annotation(self, annotation_helper: AnnotationHelper):
        annotation_helper.draw_rectangle(
            top_left=(0, 0),
            bottom_right=(1, 1),
            outline_color=dai.Color(1, 0, 0, 1),
            fill_color=dai.Color(1, 0, 0, 0.1),
            thickness=10,
        )
        annotation_helper.draw_text(
            text="Too close!",
            position=(0.3, 0.5),
            color=dai.Color(1, 0, 0, 1),
            size=64,
        )

    def _add_distance_annotation(
        self, annotation_helper: AnnotationHelper, distance: DetectionDistance
    ):
        det1 = distance.detection1
        det2 = distance.detection2
        x_start = (det1.xmin + det1.xmax) / 2
        y_start = (det1.ymin + det1.ymax) / 2
        x_end = (det2.xmin + det2.xmax) / 2
        y_end = (det2.ymin + det2.ymax) / 2
        annotation_helper.draw_line(
            pt1=(x_start, y_start),
            pt2=(x_end, y_end),
            color=PRIMARY_COLOR,
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

    @property
    def _should_alert(self) -> bool:
        return (
            len(self._state_queue) >= STATE_QUEUE_LENGTH
            and (sum(self._state_queue) / len(self._state_queue)) > ALERT_THRESHOLD
        )

    def _add_state(self, is_too_close: bool):
        self._state_queue.append(is_too_close)
        if len(self._state_queue) > STATE_QUEUE_LENGTH:
            self._state_queue.pop(0)

    def _get_all_close_detections(
        self, distances: ObjectDistances
    ) -> List[dai.SpatialImgDetection]:
        close_detections: List[dai.SpatialImgDetection] = []
        close_bboxes: List[Tuple[float, float, float, float]] = []
        for distance in distances.distances:
            if distance.distance < self.alert_distance:
                det1_bbox = (
                    distance.detection1.xmin,
                    distance.detection1.ymin,
                    distance.detection1.xmax,
                    distance.detection1.ymax,
                )
                det2_bbox = (
                    distance.detection2.xmin,
                    distance.detection2.ymin,
                    distance.detection2.xmax,
                    distance.detection2.ymax,
                )
                if det1_bbox not in close_bboxes:
                    close_detections.append(distance.detection1)
                    close_bboxes.append(det1_bbox)
                if det2_bbox not in close_bboxes:
                    close_detections.append(distance.detection2)
                    close_bboxes.append(det2_bbox)

        return close_detections
