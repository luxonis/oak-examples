import depthai as dai
import numpy as np
import cv2
from typing import List, Tuple, Optional
from depthai_nodes.utils import AnnotationHelper
from .distance_calculator import DistanceCalculator

POINT_COLOR = (0, 0.75, 1.0, 1.0)  # Brighter blue
POINT_FILL_COLOR = POINT_COLOR
BBOX_COLOR = POINT_COLOR
DISTANCE_LINE_COLOR = (0, 0.9, 1, 0.9)  # Brighter blue, more opaque
DISTANCE_TEXT_COLOR = DISTANCE_LINE_COLOR
DISTANCE_TEXT_BG_COLOR = (0, 0, 0, 0.8)


class PointTracker(dai.node.HostNode):
    bbox_increase_step = 5
    bbox_padding_step = 13
    bbox_radius = 10
    max_bbox_radius = 200
    similarity_threshold = 0.3
    debounce_threshold = 2
    motion_threshold = 0.5

    modes = {
        1: {"name": "tracking", "tracking": 2},
        2: {"name": "meter", "tracking": 1},
        3: {"name": "static", "tracking": 0},
    }

    def __init__(self, frame_width: int = 640, frame_height: int = 400):
        super().__init__()
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.input_rgb = self.createInput()
        self.input_depth = self.createInput()
        self.output_annotations = self.createOutput()

        self.points: List[dict] = []
        self.max_points = 2
        self.distance_calculator = DistanceCalculator()
        self.has_invalid_depth = False

        self.current_frame: Optional[np.ndarray] = None
        self.prev_frame: Optional[np.ndarray] = None

        self.mode = self.modes[1]

        self.latest_distance = None
        self.latest_std_dev = None

    def build(
        self, rgb_stream: dai.Node.Output, depth_stream: dai.Node.Output
    ) -> "PointTracker":
        self.link_args(rgb_stream, depth_stream)
        return self

    def set_mode(self, mode: int):
        if mode == 2:
            self.clear_points()
        self.mode = self.modes[mode]
        self.distance_calculator.clear_distances()

    def set_frame(self, frame: np.ndarray):
        self.prev_frame = self.current_frame
        self.current_frame = frame.copy() if frame is not None else None

    def add_point(self, x: float, y: float):
        frame_width, frame_height = self.frame_width, self.frame_height
        pixel_x = int(x * frame_width)
        pixel_y = int(y * frame_height)

        if len(self.points) >= self.max_points:
            self.clear_points()

        if self.current_frame is None:
            self._add_simple_point(pixel_x, pixel_y)
            return

        try:
            bbox_radius = self._calculate_bbox_radius((pixel_x, pixel_y))

            x1 = max(0, pixel_x - bbox_radius)
            y1 = max(0, pixel_y - bbox_radius)
            x2 = min(frame_width, pixel_x + bbox_radius)
            y2 = min(frame_height, pixel_y + bbox_radius)

            bbox = (x1, y1, x2 - x1, y2 - y1)

            tracker = cv2.TrackerCSRT.create()

            if tracker is None:
                raise ValueError("No tracker available")

            x, y, w, h = bbox
            if (
                x < 0
                or y < 0
                or w <= 0
                or h <= 0
                or x + w > self.current_frame.shape[1]
                or y + h > self.current_frame.shape[0]
            ):
                raise ValueError("Bbox out of bounds or invalid dimensions")

            if self.current_frame.dtype != np.uint8:
                frame_for_tracker = (
                    (self.current_frame * 255).astype(np.uint8)
                    if self.current_frame.dtype == np.float32
                    else self.current_frame.astype(np.uint8)
                )
            else:
                frame_for_tracker = self.current_frame.copy()

            if len(frame_for_tracker.shape) == 3 and frame_for_tracker.shape[2] == 3:
                pass
            elif len(frame_for_tracker.shape) == 2:
                frame_for_tracker = cv2.cvtColor(frame_for_tracker, cv2.COLOR_GRAY2BGR)

            try:
                tracker.init(frame_for_tracker, bbox)
                success = True
            except Exception:
                success = False

            if success:
                # Extract ROI for comparison
                x, y, w, h = bbox
                roi = (
                    self.current_frame[y : y + h, x : x + w]
                    if y + h <= self.current_frame.shape[0]
                    and x + w <= self.current_frame.shape[1]
                    else None
                )

                point_data = {
                    "bbox": bbox,
                    "tracker": tracker,
                    "roi": roi,
                    "pixel_coords": (pixel_x, pixel_y),
                }
                self.points.append(point_data)
            else:
                self._add_simple_point(pixel_x, pixel_y)

        except Exception as e:
            print(f"Error adding point: {e}, pixel_x: {pixel_x}, pixel_y: {pixel_y}")
            self._add_simple_point(pixel_x, pixel_y)

    def _add_simple_point(self, pixel_x: int, pixel_y: int):
        bbox_size = 20
        bbox = (
            max(0, pixel_x - bbox_size // 2),
            max(0, pixel_y - bbox_size // 2),
            bbox_size,
            bbox_size,
        )

        point_data = {
            "bbox": bbox,
            "tracker": None,
            "roi": None,
            "pixel_coords": (pixel_x, pixel_y),
        }
        self.points.append(point_data)

    def _calculate_bbox_radius(self, point: Tuple[int, int]) -> int:
        if self.current_frame is None:
            return self.bbox_radius

        bbox_radius = self.bbox_radius

        while bbox_radius < self.max_bbox_radius:
            # Create test bbox
            x, y = point
            x1 = max(0, x - bbox_radius)
            y1 = max(0, y - bbox_radius)
            x2 = min(self.current_frame.shape[1], x + bbox_radius)
            y2 = min(self.current_frame.shape[0], y + bbox_radius)

            test_bbox = (x1, y1, x2 - x1, y2 - y1)

            # Extract ROI and calculate edge density
            roi_x, roi_y, roi_w, roi_h = test_bbox
            if (
                roi_y + roi_h <= self.current_frame.shape[0]
                and roi_x + roi_w <= self.current_frame.shape[1]
            ):
                roi = self.current_frame[roi_y : roi_y + roi_h, roi_x : roi_x + roi_w]
                edge_density = self._get_edge_density(roi)

                if edge_density > 0.1:
                    break

            bbox_radius += self.bbox_increase_step

        return bbox_radius + self.bbox_padding_step

    def _get_edge_density(self, roi: np.ndarray) -> float:
        if roi is None or roi.size == 0:
            return 0.0

        # Convert to grayscale if needed
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if len(roi.shape) == 3 else roi
        edges = cv2.Canny(gray, 100, 200)
        return np.sum(edges) / (roi.shape[0] * roi.shape[1]) if roi.size > 0 else 0.0

    def update_tracking(self):
        if not self.points or self.current_frame is None:
            return

        for i, point_data in enumerate(self.points):
            tracker = point_data.get("tracker")
            old_bbox = point_data["bbox"]

            if tracker is None:
                continue

            if self.mode["tracking"] == 2 or (self.mode["tracking"] == 1 and i == 1):
                try:
                    success, new_bbox = tracker.update(self.current_frame)
                except Exception:
                    continue

                if success and not self._is_bbox_out_of_frame(new_bbox):
                    if (
                        self._debounce(old_bbox, new_bbox)
                        and self._calculate_global_motion() < self.motion_threshold
                    ):
                        new_bbox = old_bbox  # Keep old bbox

                    point_data["bbox"] = new_bbox

                    x, y, w, h = [int(v) for v in new_bbox]
                    if (
                        y + h <= self.current_frame.shape[0]
                        and x + w <= self.current_frame.shape[1]
                    ):
                        point_data["roi"] = self.current_frame[y : y + h, x : x + w]

                        point_data["pixel_coords"] = (x + w // 2, y + h // 2)

    def _debounce(self, old_bbox: Tuple, new_bbox: Tuple) -> bool:
        return all(
            abs(old_bbox[i] - new_bbox[i]) < self.debounce_threshold for i in range(4)
        )

    def _is_bbox_out_of_frame(self, bbox: Tuple) -> bool:
        if self.current_frame is None:
            return True
        x, y, w, h = bbox
        return (
            x < 0
            or y < 0
            or x + w > self.current_frame.shape[1]
            or y + h > self.current_frame.shape[0]
        )

    def _calculate_global_motion(self) -> float:
        if self.prev_frame is None or self.current_frame is None:
            return 0.0

        # Convert to grayscale
        prev_gray = (
            cv2.cvtColor(self.prev_frame, cv2.COLOR_BGR2GRAY)
            if len(self.prev_frame.shape) == 3
            else self.prev_frame
        )
        curr_gray = (
            cv2.cvtColor(self.current_frame, cv2.COLOR_BGR2GRAY)
            if len(self.current_frame.shape) == 3
            else self.current_frame
        )

        # Subsample for performance
        subsample_factor = 10
        prev_sub = prev_gray[::subsample_factor, ::subsample_factor]
        curr_sub = curr_gray[::subsample_factor, ::subsample_factor]

        try:
            flow = cv2.calcOpticalFlowFarneback(
                prev_sub,
                curr_sub,
                None,
                pyr_scale=0.5,
                levels=1,
                winsize=13,
                iterations=2,
                poly_n=5,
                poly_sigma=1.1,
                flags=0,
            )

            motion_magnitude = np.sqrt(flow[..., 0] ** 2 + flow[..., 1] ** 2)
            return np.mean(motion_magnitude)
            # print(mean_motion)
        except Exception:
            return 0.0

    def clear_points(self):
        self.points.clear()
        self.latest_distance = None
        self.latest_std_dev = None
        self.has_invalid_depth = False
        self.distance_calculator.clear_distances()

    def get_latest_distance(self):
        return {
            "distance": self.latest_distance,
            "std_deviation": self.latest_std_dev,
            "point_count": len(self.points),
            "has_invalid_depth": self.has_invalid_depth,
        }

    def create_annotations(self, rgb_msg) -> dai.ImgAnnotations:
        helper = AnnotationHelper()

        for i, point_data in enumerate(self.points):
            pixel_coords = point_data.get("pixel_coords", (0, 0))
            bbox = point_data.get("bbox", (0, 0, 10, 10))
            norm_x = pixel_coords[0] / self.frame_width
            norm_y = pixel_coords[1] / self.frame_height

            if self.mode["tracking"] > 0:
                bbox_x, bbox_y, bbox_w, bbox_h = bbox

                norm_x1 = bbox_x / self.frame_width
                norm_y1 = bbox_y / self.frame_height
                norm_x2 = (bbox_x + bbox_w) / self.frame_width
                norm_y2 = (bbox_y + bbox_h) / self.frame_height

                helper.draw_rectangle(
                    top_left=(norm_x1, norm_y1),
                    bottom_right=(norm_x2, norm_y2),
                    outline_color=BBOX_COLOR,
                    thickness=2,
                )

            helper.draw_circle(
                center=(norm_x, norm_y),
                radius=0.008,
                outline_color=POINT_COLOR,
                fill_color=POINT_FILL_COLOR,
                thickness=2,
            )

        if len(self.points) == 2:
            p1_coords = self.points[0].get("pixel_coords", (0, 0))
            p2_coords = self.points[1].get("pixel_coords", (0, 0))

            # convrt to normalized coordinates
            norm_p1 = (
                p1_coords[0] / self.frame_width,
                p1_coords[1] / self.frame_height,
            )
            norm_p2 = (
                p2_coords[0] / self.frame_width,
                p2_coords[1] / self.frame_height,
            )

            helper.draw_line(
                pt1=norm_p1, pt2=norm_p2, color=DISTANCE_LINE_COLOR, thickness=3
            )

        return helper.build(rgb_msg.getTimestamp(), rgb_msg.getSequenceNum())

    def process(self, rgb_msg, depth_msg):
        try:
            if rgb_msg is not None and depth_msg is not None:
                self.frame_width = rgb_msg.getWidth()
                self.frame_height = rgb_msg.getHeight()
                rgb_frame = rgb_msg.getCvFrame()
                if rgb_frame is not None:
                    bgr_frame = cv2.cvtColor(rgb_frame, cv2.COLOR_RGB2BGR)
                    self.set_frame(bgr_frame)
                    self.update_tracking()

                annotations = self.create_annotations(rgb_msg)
                self.output_annotations.send(annotations)

                if len(self.points) == 2:
                    distance, std_dev = self.distance_calculator.calculate_distance(
                        self.points, depth_msg
                    )

                    if distance > 0:
                        self.latest_distance = distance
                        self.latest_std_dev = std_dev
                        self.has_invalid_depth = False
                    else:
                        self.latest_distance = None
                        self.latest_std_dev = None
                        self.has_invalid_depth = True
            else:
                self.latest_distance = None
                self.latest_std_dev = None
                self.has_invalid_depth = False

        except Exception as e:
            self.latest_distance = None
            self.has_invalid_depth = True
            print(f"PointTracker processing failed: {e}")
