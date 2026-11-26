import math
from typing import Dict, Tuple

import depthai as dai

from depthai_nodes.utils import AnnotationHelper


class TrackableObject:
    def __init__(self, objectID, side):
        self.objectID = objectID
        self.side = side
        self.counted = False


class AnnotationNode(dai.node.HostNode):
    def __init__(self) -> None:
        super().__init__()
        self._axis = "x"
        self._roi_position = 0.5
        self._crossing_margin = 0.02
        self._trackable_objects: Dict[int, TrackableObject] = {}
        self._counter = [0, 0, 0, 0]

    def build(
        self,
        tracklets: dai.Node.Output,
        axis: str = None,
        roi_position: float = None,
        crossing_margin: float = None,
    ) -> "AnnotationNode":
        self.link_args(tracklets)
        if axis is not None:
            self.set_axis(axis)
        if roi_position is not None:
            self.set_roi_position(roi_position)
        if crossing_margin is not None:
            self.set_crossing_margin(crossing_margin)
        return self

    def set_axis(self, axis: str) -> None:
        if axis not in ["x", "y"]:
            raise ValueError("Axis must be either 'x' or 'y'.")
        self._axis = axis

    def set_roi_position(self, roi_position: float) -> None:
        if roi_position < 0 or roi_position > 1:
            raise ValueError("ROI position must be between 0 and 1.")
        self._roi_position = roi_position

    def set_crossing_margin(self, crossing_margin: float) -> None:
        if not math.isfinite(crossing_margin) or not 0 <= crossing_margin < 0.5:
            raise ValueError("Crossing margin must be between 0 and 0.5.")
        self._crossing_margin = crossing_margin

    def process(self, tracklets: dai.Buffer) -> None:
        assert isinstance(tracklets, dai.Tracklets)

        self._annotations = AnnotationHelper()

        for t in tracklets.tracklets:
            if t.status == dai.Tracklet.TrackingStatus.REMOVED:
                self._trackable_objects.pop(t.id, None)
                continue
            if t.status == dai.Tracklet.TrackingStatus.LOST:
                continue

            centroid = self._calculate_centroid(t.roi)
            to = self._trackable_objects.get(t.id)
            if t.status == dai.Tracklet.TrackingStatus.NEW or to is None:
                to = TrackableObject(t.id, self._side(centroid))
                self._trackable_objects[t.id] = to
            else:
                self._update_counter(to, centroid)
            self._draw_tracklet(t.id, t.label, t.roi, centroid)

        self._draw_roi_line()
        self._draw_count_and_status()

        annotations_msg = self._annotations.build(
            timestamp=tracklets.getTimestamp(),
            sequence_num=tracklets.getSequenceNum(),
        )

        self.out.send(annotations_msg)

    def _calculate_centroid(self, roi: dai.Rect) -> Tuple[float, float]:
        x1 = roi.topLeft().x
        y1 = roi.topLeft().y
        x2 = roi.bottomRight().x
        y2 = roi.bottomRight().y
        return ((x2 - x1) / 2 + x1, (y2 - y1) / 2 + y1)

    def _side(self, centroid: Tuple[float, float]) -> int:
        position = centroid[0] if self._axis == "y" else centroid[1]
        if position < self._roi_position - self._crossing_margin:
            return -1
        if position > self._roi_position + self._crossing_margin:
            return 1
        return 0

    def _update_counter(
        self, to: TrackableObject, centroid: Tuple[float, float]
    ) -> None:
        side = self._side(centroid)
        if side == 0:
            return
        if to.side != 0 and side != to.side and not to.counted:
            index = (
                (1 if side > 0 else 0) if self._axis == "y" else (3 if side > 0 else 2)
            )
            self._counter[index] += 1
            to.counted = True
        to.side = side

    def _draw_tracklet(
        self, id: int, label: int, roi: dai.Rect, centroid: Tuple[float, float]
    ) -> None:
        self._annotations.draw_rectangle(
            roi.topLeft(), roi.bottomRight(), fill_color=None, thickness=4
        )
        self._annotations.draw_text(
            text=f"ID {id}, class {label}",
            position=centroid,
            size=24,
        )
        self._annotations.draw_circle(center=centroid, radius=0.01, thickness=3)

    def _draw_roi_line(self) -> None:
        pt1, pt2 = (
            ((self._roi_position, 0.0), (self._roi_position, 1.0))
            if self._axis == "y"
            else ((0.0, self._roi_position), (1.0, self._roi_position))
        )
        self._annotations.draw_line(pt1, pt2, thickness=6)

    def _draw_count_and_status(self) -> None:
        text = (
            f"Left: {self._counter[0]}; Right: {self._counter[1]}"
            if self._axis == "y"
            else f"Up: {self._counter[2]}; Down: {self._counter[3]}"
        )
        self._annotations.draw_text(
            text=text,
            position=(0.1, 0.1),
            size=36,
        )
