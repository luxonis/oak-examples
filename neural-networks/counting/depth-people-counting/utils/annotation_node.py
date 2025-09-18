from typing import Dict, Tuple
import numpy as np
import depthai as dai

from depthai_nodes.utils import AnnotationHelper


# from https://www.pyimagesearch.com/2018/08/13/opencv-people-counter/
class TrackableObject:
    def __init__(self, objectID, centroid):
        self.objectID = objectID
        self.centroids = [centroid]
        self.counted = False


class AnnotationNode(dai.node.HostNode):
    def __init__(self) -> None:
        super().__init__()
        self._axis = "x"
        self._axis_position = 0.5
        self._trackable_objects: Dict[int, TrackableObject] = {}
        self._counter = [0, 0, 0, 0]

    def build(
        self,
        tracklets: dai.Node.Output,
        axis: bool = None,
        axis_position: float = None,
    ) -> "AnnotationNode":
        self.link_args(tracklets)
        if axis is not None:
            self.set_axis(axis)
        if axis_position is not None:
            self.set_axis_position(axis_position)
        return self

    def set_axis(self, axis: str) -> None:
        if axis not in ["x", "y"]:
            raise ValueError("Axis must be either 'x' or 'y'.")
        self._axis = axis

    def set_axis_position(self, axis_position: float) -> None:
        if axis_position < 0 or axis_position > 1:
            raise ValueError("Axis position must be between 0 and 1.")
        self._axis_position = axis_position

    def process(self, tracklets: dai.Buffer) -> None:
        assert isinstance(tracklets, dai.Tracklets)

        self._annotations = AnnotationHelper()

        for t in tracklets.tracklets:
            to = self._trackable_objects.get(t.id, None)
            centroid = self._calculate_centroid(t.roi)

            if t.status == dai.Tracklet.TrackingStatus.NEW:
                to = TrackableObject(t.id, centroid)
            elif isinstance(to, TrackableObject):
                self._update_counter(to, centroid)
                to.centroids.append(centroid)

            self._trackable_objects[t.id] = to

            if (
                t.status != dai.Tracklet.TrackingStatus.LOST
                and t.status != dai.Tracklet.TrackingStatus.REMOVED
            ):
                self._draw_tracklet(t.id, centroid)

        self._draw_axis()
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

    def _update_counter(self, to: TrackableObject, centroid: Tuple[int, int]) -> None:
        if self._axis == "y" and not to.counted:
            x = [c[0] for c in to.centroids]
            direction = centroid[0] - np.mean(x)

            if (
                centroid[0] > self._axis_position
                and direction > 0
                and np.mean(x) < self._axis_position
            ):
                self._counter[1] += 1
                to.counted = True
            elif (
                centroid[0] < self._axis_position
                and direction < 0
                and np.mean(x) > self._axis_position
            ):
                self._counter[0] += 1
                to.counted = True

        elif self._axis == "x" and not to.counted:
            y = [c[1] for c in to.centroids]
            direction = centroid[1] - np.mean(y)

            if (
                centroid[1] > self._axis_position
                and direction > 0
                and np.mean(y) < self._axis_position
            ):
                self._counter[3] += 1
                to.counted = True
            elif (
                centroid[1] < self._axis_position
                and direction < 0
                and np.mean(y) > self._axis_position
            ):
                self._counter[2] += 1
                to.counted = True

    def _draw_tracklet(self, id: int, centroid: Tuple[float, float]) -> None:
        self._annotations.draw_text(
            text="ID {}".format(id),
            position=centroid,
            size=8,
        )
        self._annotations.draw_circle(center=centroid, radius=0.02, thickness=4)

    def _draw_axis(self) -> None:
        pt1, pt2 = (
            ((self._axis_position, 0.0), (self._axis_position, 1.0))
            if self._axis == "y"
            else ((0.0, self._axis_position), (1.0, self._axis_position))
        )
        self._annotations.draw_line(pt1, pt2)

    def _draw_count_and_status(self) -> None:
        text = (
            f"Left: {self._counter[0]}; Right: {self._counter[1]}"
            if self._axis == "y"
            else f"Up: {self._counter[2]}; Down: {self._counter[3]}"
        )
        self._annotations.draw_text(
            text=text,
            position=(0.1, 0.1),
            size=16,
        )
