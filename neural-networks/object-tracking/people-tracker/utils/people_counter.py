from datetime import timedelta

import depthai as dai

from depthai_nodes.utils import AnnotationHelper


class PeopleCounter(dai.node.HostNode):
    def __init__(self) -> None:
        super().__init__()
        self.tracking_data = {}
        # Y axis (up/down), X axis (left/right)
        self.counter = {"up": 0, "down": 0, "left": 0, "right": 0}
        self.output = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.ImgFrame, True)
            ]
        )

    def build(self, tracklets: dai.Node.Output, threshold: float) -> "PeopleCounter":
        self.link_args(tracklets)

        self._threshold = threshold
        return self

    def process(self, tracklets: dai.Tracklets) -> None:
        self.update(tracklets)
        annots = self.get_img_annotations(
            tracklets.getTimestamp(), tracklets.getSequenceNum()
        )
        self.out.send(annots)

    def update(self, tracklets: dai.Tracklets) -> None:
        for t in tracklets.tracklets:
            id = str(t.id)
            centroid = get_centroid(t.roi)

            # New tracklet, save its centroid
            if t.status == dai.Tracklet.TrackingStatus.NEW:
                self.tracking_data[id] = {}  # Reset
                self.tracking_data[id]["coords"] = centroid

            elif t.status == dai.Tracklet.TrackingStatus.TRACKED:
                self.tracking_data[id]["lost_count"] = 0

            elif t.status == dai.Tracklet.TrackingStatus.LOST:
                self.tracking_data[id]["lost_count"] += 1

                # Removes tracklet that has been lost for more than 10 frames
                if (
                    self.tracking_data[id]["lost_count"] > 10
                    and "lost" not in self.tracking_data[id]
                ):
                    self.terminate_tracklet(id, centroid)
                    self.tracking_data[id]["lost"] = True

            elif (
                t.status == dai.Tracklet.TrackingStatus.REMOVED
            ) and "lost" not in self.tracking_data[id]:
                self.terminate_tracklet(id, centroid)

    def get_img_annotations(self, timestamp: timedelta, sequence_num: int):
        annotation_helper = AnnotationHelper()

        annotation_helper.draw_text(
            text=f"Up: {self.counter['up']}, Down: {self.counter['down']}, Left: {self.counter['left']}, Right: {self.counter['right']}",
            position=(0.05, 0.05),
            size=25,
        )

        annotations = annotation_helper.build(
            timestamp=timestamp,
            sequence_num=sequence_num,
        )
        return annotations

    def terminate_tracklet(self, id, coords_end):
        coords_start = self.tracking_data[id]["coords"]

        dx = coords_end[0] - coords_start[0]
        dy = coords_end[1] - coords_start[1]

        if abs(dx) > abs(dy) and abs(dx) > self._threshold:
            direction = "left" if dx < 0 else "right"
            self.counter[direction] += 1
            print(f"Person moved {direction}")

        elif abs(dy) > abs(dx) and abs(dy) > self._threshold:
            direction = "up" if dy < 0 else "down"
            self.counter[direction] += 1
            print(f"Person moved {direction}")


def get_centroid(roi):
    x1 = roi.topLeft().x
    y1 = roi.topLeft().y
    x2 = roi.bottomRight().x
    y2 = roi.bottomRight().y
    return (x2 - x1) / 2 + x1, (y2 - y1) / 2 + y1
