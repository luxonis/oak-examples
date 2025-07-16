import depthai as dai
from depthai_nodes.utils import AnnotationHelper
import numpy as np
import collections
from typing import Dict, List, Any

from . import config
from .detection_object import WorldDetection
from .fusion import DetectionGroupBuffer


class BirdsEyeView(dai.node.HostNode):
    ANNOT_COLORS = {
        "white": (1.0, 1.0, 1.0, 1.0),
        "red": (1.0, 0.0, 0.0, 1.0),
        "green": (0.0, 1.0, 0.0, 1.0),
        "trail": (0.5, 0.5, 0.5, 1.0),
    }

    def __init__(self):
        super().__init__()
        self.all_cam_extrinsics = {}
        self.canvas = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.ImgFrame, True)
            ]
        )
        self.cameras_pos = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.ImgAnnotations, True)
            ]
        )
        self.history_trails = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.ImgAnnotations, True)
            ]
        )
        self.detections = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.ImgAnnotations, True)
            ]
        )

    def build(
        self, all_cam_extrinsics: Dict[str, Dict[str, Any]], detections: dai.Node.Output
    ) -> "BirdsEyeView":
        self.all_cam_extrinsics = all_cam_extrinsics
        self.width, self.height, self.scale = (
            config.BEV_WIDTH,
            config.BEV_HEIGHT,
            config.BEV_SCALE,
        )
        self.history = collections.deque(maxlen=config.TRAIL_LENGTH)
        self.world_to_bev_transform = np.array(
            [[self.scale, 0, 0, self.width / 2], [0, self.scale, 0, self.height / 2]]
        )

        self.camera_colors = [
            (1.0, 0.0, 1.0, 1.0),  # Magenta
            (0.0, 1.0, 1.0, 1.0),  # Cyan
            (1.0, 1.0, 0.0, 1.0),  # Yellow
            (0.0, 0.0, 1.0, 1.0),  # Blue
            (0.0, 1.0, 0.0, 1.0),  # Green
        ]
        self.link_args(detections)
        return self

    def process(self, detections_buffer: dai.Buffer):
        assert isinstance(detections_buffer, DetectionGroupBuffer)
        groups: List[List[WorldDetection]] = detections_buffer.groups
        if config.BEV_LABELS:
            filtered_groups = [
                filtered_grp
                for grp in groups
                if (
                    filtered_grp := [
                        det for det in grp if det.label.lower() in config.BEV_LABELS
                    ]
                )
            ]
        else:
            filtered_groups = groups
        self.history.append(filtered_groups)

        timestamp = detections_buffer.getTimestamp()
        sequence_num = detections_buffer.getSequenceNum()

        canvas_frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        canvas_msg = dai.ImgFrame()
        canvas_msg.setTimestamp(timestamp)
        canvas_msg.setSequenceNum(sequence_num)
        canvas_msg.setCvFrame(canvas_frame, dai.ImgFrame.Type.BGR888p)
        self.canvas.send(canvas_msg)

        w_norm, h_norm = 1 / self.width, 1 / self.height

        cam_helper = self._create_camera_annotations(w_norm, h_norm)
        self.cameras_pos.send(cam_helper.build(timestamp, sequence_num))

        trail_helper = self._create_trail_annotations(w_norm, h_norm)
        self.history_trails.send(trail_helper.build(timestamp, sequence_num))

        det_helper = self._create_detection_annotations(filtered_groups, w_norm, h_norm)
        self.detections.send(det_helper.build(timestamp, sequence_num))

    def _create_camera_annotations(
        self, w_norm: float, h_norm: float
    ) -> AnnotationHelper:
        """Draws static elements: camera positions, FOV cones, and world axes."""
        helper = AnnotationHelper()

        # World axes
        origin = self._project_to_bev(np.array([0, 0, 0, 1]))
        x_axis = self._project_to_bev(np.array([1, 0, 0, 1]))
        y_axis = self._project_to_bev(np.array([0, 1, 0, 1]))
        helper.draw_line(
            (origin[0] * w_norm, origin[1] * h_norm),
            (x_axis[0] * w_norm, x_axis[1] * h_norm),
            self.ANNOT_COLORS["red"],
            thickness=2,
        )
        helper.draw_line(
            (origin[0] * w_norm, origin[1] * h_norm),
            (y_axis[0] * w_norm, y_axis[1] * h_norm),
            self.ANNOT_COLORS["green"],
            thickness=2,
        )

        # Cameras & FOV cones
        for _, extr in self.all_cam_extrinsics.items():
            fid = extr["friendly_id"]
            cam_color = self.camera_colors[(fid - 1) % len(self.camera_colors)]
            p0 = self._project_to_bev(extr["cam_to_world"] @ np.array([0, 0, 0, 1]))
            p1 = self._project_to_bev(extr["cam_to_world"] @ np.array([0.2, 0, 0.1, 1]))
            p2 = self._project_to_bev(
                extr["cam_to_world"] @ np.array([-0.2, 0, 0.1, 1])
            )

            # Draw camera position as an ellipse
            cam_points = self._get_ellipse_points((p0[0], p0[1]), 5, 5, w_norm, h_norm)
            helper.draw_polyline(
                cam_points, cam_color, fill_color=cam_color, closed=True
            )
            # Draw FOV lines
            helper.draw_line(
                (p0[0] * w_norm, p0[1] * h_norm),
                (p1[0] * w_norm, p1[1] * h_norm),
                cam_color,
                2,
            )
            helper.draw_line(
                (p0[0] * w_norm, p0[1] * h_norm),
                (p2[0] * w_norm, p2[1] * h_norm),
                cam_color,
                2,
            )

        return helper

    def _create_trail_annotations(
        self, w_norm: float, h_norm: float
    ) -> AnnotationHelper:
        """Draws historical trails of detected objects."""
        helper = AnnotationHelper()
        base_trail_brightness = self.ANNOT_COLORS["trail"][0]
        radius_px = 25

        for i, frame_groups in enumerate(self.history):
            # Calculate brightness based on age. Oldest (i=0) is darkest.
            brightness = (i / max(1, self.history.maxlen)) * base_trail_brightness
            trail_color = (brightness, brightness, brightness, 1)

            for group in frame_groups:
                if not group:
                    continue
                avg_pos = np.mean([d.pos_world_homogeneous for d in group], axis=0)
                u, v = self._project_to_bev(avg_pos)
                trail_points = self._get_ellipse_points(
                    (u, v), radius_px, radius_px, w_norm, h_norm
                )
                helper.draw_polyline(
                    trail_points,
                    trail_color,
                    fill_color=trail_color,
                    thickness=0,
                    closed=True,
                )
        return helper

    def _create_detection_annotations(
        self, groups: List[List[WorldDetection]], w_norm: float, h_norm: float
    ) -> AnnotationHelper:
        """Draws the current, live detections with colored dots and white rings."""
        helper = AnnotationHelper()
        detection_dot_radius_px = 6

        for grp in groups:
            if not grp:
                continue
            # Draw individual detection dots
            for det in grp:
                u, v = self._project_to_bev(det.pos_world_homogeneous)
                cam_col = self.camera_colors[
                    (det.camera_friendly_id - 1) % len(self.camera_colors)
                ]
                ellipse_points = self._get_ellipse_points(
                    (u, v),
                    detection_dot_radius_px,
                    detection_dot_radius_px,
                    w_norm,
                    h_norm,
                )
                helper.draw_polyline(
                    points=ellipse_points,
                    outline_color=cam_col,
                    fill_color=cam_col,
                    thickness=1,
                    closed=True,
                )

            # Calculate and draw the ring
            avg_pos = np.mean([d.pos_world_homogeneous for d in grp], axis=0)
            u_avg, v_avg = self._project_to_bev(avg_pos)
            center_px = (u_avg, v_avg)

            if len(grp) > 1:
                distances_m = [
                    np.linalg.norm(det.pos_world_homogeneous[:2] - avg_pos[:2])
                    for det in grp
                ]
                dist_to_furthest_center_m = max(distances_m)
            else:
                dist_to_furthest_center_m = 0

            dist_to_furthest_center_px = dist_to_furthest_center_m * self.scale
            margin_px = 12
            total_radius_px = (
                dist_to_furthest_center_px + detection_dot_radius_px + margin_px
            )

            ring_points = self._get_ellipse_points(
                center_px, total_radius_px, total_radius_px, w_norm, h_norm
            )
            helper.draw_polyline(
                ring_points, self.ANNOT_COLORS["white"], thickness=2, closed=True
            )

            # Draw the label
            text_offset_h = (total_radius_px + 15) * h_norm
            text_n = (center_px[0] * w_norm, center_px[1] * h_norm - text_offset_h)
            helper.draw_text(grp[0].label, text_n, self.ANNOT_COLORS["white"], size=14)

        return helper

    def _project_to_bev(self, pos: np.ndarray) -> tuple[int, int]:
        """Projects a 3D world position to 2D BEV coordinates."""
        uv = self.world_to_bev_transform @ pos.reshape(4, 1)
        return int(uv[0]), int(uv[1])

    def _get_ellipse_points(
        self, center_px, radius_px_x, radius_px_y, w_norm, h_norm, segments=20
    ):
        """Generates normalized points for an ellipse."""
        points = []
        for i in range(segments + 1):
            theta = 2 * np.pi * (i / segments)
            x = center_px[0] + radius_px_x * np.cos(theta)
            y = center_px[1] + radius_px_y * np.sin(theta)
            points.append((x * w_norm, y * h_norm))
        return points
