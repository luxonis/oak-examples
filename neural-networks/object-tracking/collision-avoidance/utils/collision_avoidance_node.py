import numpy as np
import depthai as dai

from depthai_nodes.utils import AnnotationHelper
from depthai_nodes import SECONDARY_COLOR

import math
import cv2

MAX_X = 5000  # mm
MAX_Z = 15000


class CollisionAvoidanceNode(dai.node.HostNode):
    def __init__(self):
        super().__init__()
        self.object_coordinates = {}
        self.out_direction = self.createOutput()

    def build(
        self,
        rgb: dai.Node.Output,
        tracker_out: dai.Node.Output,
    ) -> "CollisionAvoidanceNode":
        self.link_args(rgb, tracker_out)
        return self

    def moving_forward(self, tracklet_id, moving_threshold=100):
        z_values = self.object_coordinates[tracklet_id]["z"]
        if len(z_values) < 2:
            return False
        if z_values[-1] < z_values[0] - moving_threshold:
            return True
        return False

    def calculate_metrics(self, tracklet_id):
        x1 = self.object_coordinates[tracklet_id]["x"][0]
        z1 = self.object_coordinates[tracklet_id]["z"][0]
        x2 = self.object_coordinates[tracklet_id]["x"][-1]
        z2 = self.object_coordinates[tracklet_id]["z"][-1]
        timestamp1 = self.object_coordinates[tracklet_id]["timestamp"][0]
        timestamp2 = self.object_coordinates[tracklet_id]["timestamp"][-1]
        lf_distance = math.sqrt(math.pow(x1 - x2, 2) + math.pow(z1 - z2, 2))
        if lf_distance == 0:
            return 0, 0, 0
        timed = timestamp2 - timestamp1
        speed = lf_distance / timed  # m/s
        target_distance = math.sqrt(math.pow(x2, 2) + math.pow(z2, 2))
        tti = target_distance / speed
        return speed, target_distance, tti

    def draw_line_cv2(
        self, mbs, width=400, height=400, line_color=(0, 255, 0), thickness=2
    ):
        image = np.ones((height, width, 3), dtype=np.uint8) * 255

        for m, b in mbs:
            # Calculate the center point
            center_x = width // 2
            center_y = height // 2

            # Calculate the end point using the slope
            # For a line with slope m, the change in y is m times the change in x
            # We'll use line_length/2 to determine how far to go in the x direction
            dx = width // 2
            dy = int(m * dx)

            # Calculate the end points (in both directions from the center)
            end_x1 = center_x + dx
            end_y1 = center_y + dy
            end_x2 = center_x - dx
            end_y2 = center_y - dy

            # Draw the line
            cv2.line(image, (end_x1, end_y1), (end_x2, end_y2), line_color, thickness)

            # Mark the center point
            cv2.circle(image, (center_x, center_y), 5, (0, 255, 0), -1)

        return image

    def process(self, img_frame: dai.Buffer, tracklets: dai.Buffer) -> None:
        assert isinstance(img_frame, dai.ImgFrame)
        assert isinstance(tracklets, dai.Tracklets)

        annotation_helper = AnnotationHelper()

        mbs = []

        for tracklet in tracklets.tracklets:
            xmin = tracklet.roi.topLeft().x
            ymin = tracklet.roi.topLeft().y
            xmax = tracklet.roi.bottomRight().x
            ymax = tracklet.roi.bottomRight().y

            if tracklet.id not in self.object_coordinates:
                self.object_coordinates[tracklet.id] = {
                    "x": [tracklet.spatialCoordinates.x],
                    "z": [tracklet.spatialCoordinates.z],
                    "timestamp": [tracklets.getTimestamp().total_seconds()],
                }
            else:
                self.object_coordinates[tracklet.id]["x"].append(
                    tracklet.spatialCoordinates.x
                )
                self.object_coordinates[tracklet.id]["z"].append(
                    tracklet.spatialCoordinates.z
                )
                self.object_coordinates[tracklet.id]["timestamp"].append(
                    tracklets.getTimestamp().total_seconds()
                )

            if len(self.object_coordinates[tracklet.id]["x"]) > 10:
                # we have enough data to fit a line
                self.object_coordinates[tracklet.id]["x"].pop(0)
                self.object_coordinates[tracklet.id]["z"].pop(0)
                try:
                    m, b = np.polyfit(
                        self.object_coordinates[tracklet.id]["x"],
                        self.object_coordinates[tracklet.id]["z"],
                        1,
                    )
                    distance = abs(b) / math.sqrt(math.pow(m, 2) + 1)
                    mbs.append((m, b))

                    speed, target_distance, tti = self.calculate_metrics(tracklet.id)
                    annotation_helper.draw_text(
                        text=f"Speed: {speed}\nTarget Distance: {target_distance}\nTTI: {tti}",
                        position=(xmin + 0.01, ymin + 0.12),
                        color=SECONDARY_COLOR,
                        size=8,
                    )

                    if distance < 200 and self.moving_forward(tracklet.id):
                        annotation_helper.draw_text(
                            text="DANGER",
                            position=(0.3, 0.6),
                            color=(1, 0, 0, 1),
                            size=64,
                        )
                except np.linalg.LinAlgError:
                    pass

            annotation_helper.draw_rectangle(
                top_left=(xmin, ymin),
                bottom_right=(xmax, ymax),
                thickness=2,
            )

            annotation_helper.draw_text(
                text=f"ID: {tracklet.id}",
                position=(xmin + 0.01, ymin + 0.04),
                color=SECONDARY_COLOR,
                size=8,
            )

        annotations = annotation_helper.build(
            timestamp=tracklets.getTimestamp(), sequence_num=tracklets.getSequenceNum()
        )
        self.out.send(annotations)

        direction_frame = self.draw_line_cv2(mbs)
        frame_msg = dai.ImgFrame()
        frame_msg.setCvFrame(direction_frame, dai.ImgFrame.Type.BGR888i)
        frame_msg.setWidth(400)
        frame_msg.setHeight(400)
        self.out_direction.send(frame_msg)
