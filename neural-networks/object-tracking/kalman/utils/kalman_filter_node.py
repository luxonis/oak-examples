import numpy as np
import depthai as dai
from typing import List

from .kalman_filter import KalmanFilter

from depthai_nodes.utils import AnnotationHelper
from depthai_nodes import PRIMARY_COLOR, SECONDARY_COLOR


class KalmanFilterNode(dai.node.HostNode):
    def __init__(self):
        self._kalman_filters = {}
        super().__init__()

    def build(
        self,
        rgb: dai.Node.Output,
        tracker_out: dai.Node.Output,
        baseline: float,
        focal_length: float,
        label_map: List[str],
    ) -> "KalmanFilterNode":
        self.link_args(rgb, tracker_out)
        self._baseline = baseline
        self._focal_length = focal_length
        self._label_map = label_map
        return self

    def process(self, img_frame: dai.Buffer, tracklets: dai.Buffer) -> None:
        assert isinstance(img_frame, dai.ImgFrame)
        assert isinstance(tracklets, dai.Tracklets)
        frame: np.ndarray = img_frame.getCvFrame()
        current_time = tracklets.getTimestamp()

        annotation_helper = AnnotationHelper()

        for t in tracklets.tracklets:
            roi = t.roi.denormalize(frame.shape[1], frame.shape[0])
            x1 = int(roi.topLeft().x)
            y1 = int(roi.topLeft().y)
            x2 = int(roi.bottomRight().x)
            y2 = int(roi.bottomRight().y)

            x_space = t.spatialCoordinates.x
            y_space = t.spatialCoordinates.y
            z_space = t.spatialCoordinates.z

            meas_vec_bbox = np.array(
                [[(x1 + x2) / 2], [(y1 + y2) / 2], [x2 - x1], [y2 - y1]]
            )
            meas_vec_space = np.array([[x_space], [y_space], [z_space]])
            meas_std_space = z_space**2 / (self._baseline * self._focal_length)

            if t.status.name == "NEW":
                # Adjust these parameters
                acc_std_space = 10
                acc_std_bbox = 0.1
                meas_std_bbox = 0.05

                self._kalman_filters[t.id] = {
                    "bbox": KalmanFilter(
                        meas_std_bbox, acc_std_bbox, meas_vec_bbox, current_time
                    ),
                    "space": KalmanFilter(
                        meas_std_space, acc_std_space, meas_vec_space, current_time
                    ),
                }

            else:
                dt = current_time - self._kalman_filters[t.id]["bbox"].time
                dt = dt.total_seconds()
                self._kalman_filters[t.id]["space"].meas_std = meas_std_space

                if t.status.name != "TRACKED":
                    meas_vec_bbox = None
                    meas_vec_space = None

                if z_space == 0:
                    meas_vec_space = None

                self._kalman_filters[t.id]["bbox"].predict(dt)
                self._kalman_filters[t.id]["bbox"].update(meas_vec_bbox)

                self._kalman_filters[t.id]["space"].predict(dt)
                self._kalman_filters[t.id]["space"].update(meas_vec_space)

                self._kalman_filters[t.id]["bbox"].time = current_time
                self._kalman_filters[t.id]["space"].time = current_time

                vec_bbox = self._kalman_filters[t.id]["bbox"].x
                vec_space = self._kalman_filters[t.id]["space"].x

                x1_filter = (vec_bbox[0] - vec_bbox[2] / 2) / img_frame.getWidth()
                x2_filter = (vec_bbox[0] + vec_bbox[2] / 2) / img_frame.getWidth()
                y1_filter = (vec_bbox[1] - vec_bbox[3] / 2) / img_frame.getHeight()
                y2_filter = (vec_bbox[1] + vec_bbox[3] / 2) / img_frame.getHeight()

                annotation_helper.draw_rectangle(
                    top_left=(x1_filter, y1_filter),
                    bottom_right=(x2_filter, y2_filter),
                    thickness=2,
                    outline_color=PRIMARY_COLOR,
                )
                annotation_helper.draw_text(
                    text=f"X: {int(vec_space[0])} mm, Y: {int(vec_space[1])} mm, Z: {int(vec_space[2])} mm",
                    position=(
                        x1 / img_frame.getWidth() + 0.02,
                        y1 / img_frame.getHeight() + 0.05,
                    ),
                    size=10,
                )
            try:
                label = self._label_map[t.label]
            except Exception:
                label = t.label

            annotation_helper.draw_text(
                text=f"ID: {t.id}, {label}, {t.status.name}",
                position=(
                    x1 / img_frame.getWidth() + 0.02,
                    y1 / img_frame.getHeight() + 0.15,
                ),
                size=10,
                color=SECONDARY_COLOR,
            )

            annotation_helper.draw_rectangle(
                top_left=(x1 / img_frame.getWidth(), y1 / img_frame.getHeight()),
                bottom_right=(x2 / img_frame.getWidth(), y2 / img_frame.getHeight()),
                thickness=2,
                outline_color=SECONDARY_COLOR,
            )

            annotation_helper.draw_text(
                text=f"X: {int(x_space)} mm, Y: {int(y_space)} mm, Z: {int(z_space)} mm",
                position=(
                    x1 / img_frame.getWidth() + 0.02,
                    y1 / img_frame.getHeight() + 0.1,
                ),
                size=10,
                color=SECONDARY_COLOR,
            )

        annotations = annotation_helper.build(
            timestamp=tracklets.getTimestamp(), sequence_num=tracklets.getSequenceNum()
        )
        self.out.send(annotations)
