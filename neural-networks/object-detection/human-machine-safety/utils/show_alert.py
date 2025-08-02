import depthai as dai
from utils.measure_object_distance import ObjectDistances
from datetime import timedelta
from typing import List
from depthai_nodes.utils import AnnotationHelper

DISTANCE_THRESHOLD = 500  # mm
ALERT_THRESHOLD = 0.3
STATE_QUEUE_LENGTH = 5


class ShowAlert(dai.node.HostNode):
    def __init__(self):
        super().__init__()
        self.output = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.ImgAnnotations, True)
            ]
        )

        self._state_queue = []

    def build(
        self,
        distances: dai.Node.Output,
        palm_label: int,
        dangerous_objects: List[int],
    ) -> "ShowAlert":
        self.link_args(distances)
        self.palm_label = palm_label
        self.dangerous_objects = dangerous_objects
        return self

    def process(self, distances: dai.Buffer):
        assert isinstance(distances, ObjectDistances)
        found_close_dets = False
        for distance in distances.distances:
            if (
                (
                    distance.detection1.label == self.palm_label
                    and distance.detection2.label in self.dangerous_objects
                )
                or (
                    distance.detection2.label == self.palm_label
                    and distance.detection1.label in self.dangerous_objects
                )
            ) and distance.distance < DISTANCE_THRESHOLD:
                found_close_dets = True
                break
        self._state_queue.append(found_close_dets)

        if len(self._state_queue) > STATE_QUEUE_LENGTH:
            self._state_queue.pop(0)
        if self._should_alert:
            img_annotations = self._draw_alert(
                distances.getTimestamp(), distances.getSequenceNum()
            )
            self.output.send(img_annotations)

    @property
    def _should_alert(self) -> bool:
        return sum(self._state_queue) / len(self._state_queue) > ALERT_THRESHOLD

    def _draw_alert(
        self, timestamp: timedelta, sequence_num: int
    ) -> dai.ImgAnnotations:
        annotation_helper = AnnotationHelper()
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

        img_annotations = annotation_helper.build(
            timestamp=timestamp,
            sequence_num=sequence_num,
        )
        return img_annotations
