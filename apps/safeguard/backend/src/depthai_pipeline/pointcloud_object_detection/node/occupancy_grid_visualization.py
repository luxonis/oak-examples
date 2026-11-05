import depthai as dai
import numpy as np
from depthai_nodes.utils import AnnotationHelper

from depthai_pipeline.common.message.danger_classification import DangerLevel
from settings.settings import SpatialZone
from util.danger_zones import classify_obstacle
from util.ground_alignment import ground_to_camera

from ..message import Obstacles, OccupancyMask, PlaneValidity
from .polar_grid_renderer import PolarGridRenderer


class OccupancyGridVisualizationNode(dai.node.HostNode):
    """Render the top-down occupancy grid and a point cloud zone overlay.

    The overlay includes obstacles and colored zone points when the ground
    plane is valid. A text annotation reports invalid ground estimation.
    """

    RANGE_RES = 100  # mm
    MAX_RANGE = 9000  # mm
    N_SECTORS = 17

    COLOR_DANGER = (50, 50, 230)
    COLOR_WARNING = (0, 140, 250)
    COLOR_SAFE = (60, 160, 60)

    def __init__(
        self,
        hfov_deg: float,
        danger_zone: SpatialZone,
        warning_zone: SpatialZone,
        min_visible_range_mm: float,
    ):
        super().__init__()
        self._hfov_deg = hfov_deg
        self._danger_zone = danger_zone
        self._warning_zone = warning_zone
        self._min_visible_range_mm = min_visible_range_mm

        self.out_grid = self.createOutput()
        self.out_pcl = self.createOutput()
        self.out_grid_annotations = self.createOutput()

        self._angle_bin_rad = np.radians(2.0)
        self._n_angle_bins = int(np.ceil(np.radians(hfov_deg) / self._angle_bin_rad))
        self._sector_angle_edges = np.linspace(
            -hfov_deg / 2, hfov_deg / 2, self.N_SECTORS + 1
        )
        self._sector_angle_bin_edges = np.linspace(
            0, self._n_angle_bins, self.N_SECTORS + 1
        ).astype(int)

        self._renderer = PolarGridRenderer(
            hfov_deg=hfov_deg,
            max_range=self.MAX_RANGE,
            min_visible_range=min_visible_range_mm,
            range_res=self.RANGE_RES,
            n_sectors=self.N_SECTORS,
            sector_angle_edges=self._sector_angle_edges,
            danger_zone=danger_zone,
            warning_zone=warning_zone,
            min_z_mm=min_visible_range_mm,
        )

        self._precompute_zone_pcl_points()

    def build(
        self,
        obstacles: dai.Node.Output,
        occupancy_mask: dai.Node.Output,
        plane_valid: dai.Node.Output,
        obstacle_pcl: dai.Node.Output,
    ) -> "OccupancyGridVisualizationNode":
        self.link_args(obstacles, occupancy_mask, plane_valid, obstacle_pcl)
        return self

    def process(
        self,
        obstacles_msg: dai.Buffer,
        occupancy_mask_msg: dai.Buffer,
        plane_valid_msg: dai.Buffer,
        obstacle_pcl_msg: dai.Buffer,
    ) -> None:
        try:
            assert isinstance(obstacles_msg, Obstacles)
            assert isinstance(occupancy_mask_msg, OccupancyMask)
            assert isinstance(plane_valid_msg, PlaneValidity)
            assert isinstance(obstacle_pcl_msg, dai.PointCloudData)

            occupancy_mask = np.asarray(occupancy_mask_msg.mask, dtype=bool)
            plane_valid = bool(plane_valid_msg.plane_valid)
            plane_eq = np.asarray(plane_valid_msg.plane_eq, dtype=np.float32)
            R = (
                np.asarray(plane_valid_msg.R, dtype=np.float32)
                if plane_valid and plane_valid_msg.R.size == 9
                else None
            )

            sector_nearest = self._compute_nearest_obstacle_per_sector(occupancy_mask)
            img = self._renderer.render(sector_nearest)

            out_msg = dai.ImgFrame()
            out_msg.setCvFrame(img, dai.ImgFrame.Type.BGR888i)
            out_msg.setTimestamp(obstacles_msg.getTimestamp())
            out_msg.setSequenceNum(obstacles_msg.getSequenceNum())
            self.out_grid.send(out_msg)

            pcl_msg = self._build_merged_pcl(
                obstacle_pcl_msg=obstacle_pcl_msg,
                plane_valid=plane_valid,
                plane_eq=plane_eq,
                R=R,
                timestamp=obstacles_msg.getTimestamp(),
                sequence_num=obstacles_msg.getSequenceNum(),
            )
            self.out_pcl.send(pcl_msg)

            if not plane_valid:
                grid_annotations = self._build_plane_fail_annotations(
                    timestamp=obstacles_msg.getTimestamp(),
                    sequence_num=obstacles_msg.getSequenceNum(),
                )
                self.out_grid_annotations.send(grid_annotations)
        except dai.MessageQueue.QueueException:
            return

    def _compute_nearest_obstacle_per_sector(
        self, occupancy_mask: np.ndarray
    ) -> np.ndarray:
        """Return each sector's nearest occupied range, or infinity if empty."""
        sector_nearest_ranges = np.full(self.N_SECTORS, np.inf, dtype=np.float32)

        for sector_idx in range(self.N_SECTORS):
            start_bin = self._sector_angle_bin_edges[sector_idx]
            end_bin = self._sector_angle_bin_edges[sector_idx + 1]

            sector_occupancy_mask = occupancy_mask[:, start_bin:end_bin]
            if not sector_occupancy_mask.any():
                continue

            occupied_range_rows = sector_occupancy_mask.any(axis=1)
            nearest_range_bin = int(np.argmax(occupied_range_rows))
            sector_nearest_ranges[sector_idx] = (
                nearest_range_bin + 0.5
            ) * self.RANGE_RES

        return sector_nearest_ranges

    @staticmethod
    def _rect_boundary_points(
        x_min: float, x_max: float, z_min: float, z_max: float, spacing: float
    ) -> np.ndarray:
        """Generate (x, z) points along the perimeter of a rectangle."""
        n_x = max(2, int((x_max - x_min) / spacing) + 1)
        n_z = max(2, int((z_max - z_min) / spacing) + 1)

        bottom_x = np.linspace(x_min, x_max, n_x)
        bottom_z = np.full(n_x, z_min)
        right_z = np.linspace(z_min, z_max, n_z)[1:]
        right_x = np.full(len(right_z), x_max)
        top_x = np.linspace(x_max, x_min, n_x)[1:]
        top_z = np.full(len(top_x), z_max)
        left_z = np.linspace(z_max, z_min, n_z)[1:-1]
        left_x = np.full(len(left_z), x_min)

        all_x = np.concatenate([bottom_x, right_x, top_x, left_x])
        all_z = np.concatenate([bottom_z, right_z, top_z, left_z])
        return np.column_stack([all_x, all_z]).astype(np.float32)

    @staticmethod
    def _rect_fill_points(
        x_min: float, x_max: float, z_min: float, z_max: float, spacing: float
    ) -> np.ndarray:
        """Generate (x, z) points on a regular fill lattice inside a rectangle."""
        x_vals = np.arange(x_min, x_max + 0.5 * spacing, spacing, dtype=np.float32)
        z_vals = np.arange(z_min, z_max + 0.5 * spacing, spacing, dtype=np.float32)
        xx, zz = np.meshgrid(x_vals, z_vals, indexing="xy")
        return np.column_stack((xx.ravel(), zz.ravel())).astype(np.float32)

    def _zone_fill_points(self, spacing: float) -> tuple[np.ndarray, np.ndarray]:
        """
        Return warning and danger fill points on a shared warning-zone lattice.
        Warning points exclude danger points to avoid overlap.
        """
        xz = self._rect_fill_points(
            self._warning_zone.x_min_mm,
            self._warning_zone.x_max_mm,
            self._min_visible_range_mm,
            self._warning_zone.distance_mm,
            spacing,
        )

        is_danger = (
            (xz[:, 0] >= self._danger_zone.x_min_mm)
            & (xz[:, 0] <= self._danger_zone.x_max_mm)
            & (xz[:, 1] <= self._danger_zone.distance_mm)
        )

        return xz[~is_danger], xz[is_danger]

    def _zone_boundary_points(self, spacing: float) -> tuple[np.ndarray, np.ndarray]:
        """Return warning and danger boundary perimeter points."""
        warning_boundary = self._rect_boundary_points(
            self._warning_zone.x_min_mm,
            self._warning_zone.x_max_mm,
            self._min_visible_range_mm,
            self._warning_zone.distance_mm,
            spacing,
        )
        danger_boundary = self._rect_boundary_points(
            self._danger_zone.x_min_mm,
            self._danger_zone.x_max_mm,
            self._min_visible_range_mm,
            self._danger_zone.distance_mm,
            spacing,
        )
        return warning_boundary, danger_boundary

    def _build_merged_pcl(
        self, obstacle_pcl_msg, plane_valid, plane_eq, R, timestamp, sequence_num
    ):
        """Combine obstacle and zone points in camera coordinates for display.

        Zone points are placed at the fitted plane's height. Both point sets
        are rotated back from ground coordinates for the DepthAI visualizer.
        """
        if obstacle_pcl_msg.isColor():
            obstacle_points, obstacle_colors = obstacle_pcl_msg.getPointsRGB()
        else:
            obstacle_points = obstacle_pcl_msg.getPoints()
            obstacle_colors = np.full(
                (obstacle_points.shape[0], 4), 255, dtype=np.uint8
            )

        if plane_valid and R is not None and plane_eq.size >= 4:
            # Both sets of points start in the ground-aligned frame.
            d = float(plane_eq[3])
            xz = self._zone_pcl_points
            y_ground = np.full(xz.shape[0], -d, dtype=np.float32)
            zone_points = np.column_stack([xz[:, 0], y_ground, xz[:, 1]]).astype(
                np.float32
            )

            # Rotate both clouds back to camera frame to match DepthAI Visualizer.
            if obstacle_points.shape[0] > 0:
                obstacle_points = ground_to_camera(obstacle_points, R)
            zone_points = ground_to_camera(zone_points, R)

            if obstacle_points.shape[0] > 0:
                merged_points = np.concatenate([obstacle_points, zone_points])
                merged_colors = np.concatenate([obstacle_colors, self._zone_pcl_colors])
            else:
                merged_points = zone_points
                merged_colors = self._zone_pcl_colors
        else:
            merged_points, merged_colors = obstacle_points, obstacle_colors

        msg = dai.PointCloudData()
        if merged_points.shape[0] > 0:
            msg.setPointsRGB(merged_points, merged_colors)
        else:
            msg.setPointsRGB(
                np.empty((0, 3), dtype=np.float32),
                np.empty((0, 4), dtype=np.uint8),
            )
        msg.setTimestamp(timestamp)
        msg.setSequenceNum(sequence_num)
        return msg

    def _precompute_zone_pcl_points(self) -> None:
        fill_spacing = 100.0
        boundary_spacing = 100.0

        warning_fill, danger_fill = self._zone_fill_points(fill_spacing)
        warning_boundary, danger_boundary = self._zone_boundary_points(boundary_spacing)

        warning_points = np.concatenate([warning_fill, warning_boundary], axis=0)
        danger_points = np.concatenate([danger_fill, danger_boundary], axis=0)

        warning_rgba = np.tile(
            np.array([250, 140, 0, 255], dtype=np.uint8), (warning_points.shape[0], 1)
        )
        danger_rgba = np.tile(
            np.array([230, 50, 50, 255], dtype=np.uint8), (danger_points.shape[0], 1)
        )

        self._zone_pcl_points = np.concatenate([warning_points, danger_points], axis=0)
        self._zone_pcl_colors = np.concatenate([warning_rgba, danger_rgba], axis=0)

    def _build_plane_fail_annotations(self, timestamp, sequence_num):
        helper = AnnotationHelper()
        text = "No valid ground plane - adjust camera view"
        color = self.COLOR_WARNING

        helper.draw_text(
            text=text,
            position=(0.02, 0.06),
            size=20,
            color=self._bgr_to_color(color),
        )
        return helper.build(timestamp=timestamp, sequence_num=sequence_num)

    def _build_obstacle_annotations(self, obstacles, timestamp, sequence_num):
        helper = AnnotationHelper()

        for obj in obstacles:
            zone = self._zone_of_obstacle(obj)
            annot_color = self._bgr_to_color(self._zone_color(zone))

            if obj.bbox is not None:
                tl = (obj.bbox.x_min, obj.bbox.y_min)
                br = (obj.bbox.x_max, obj.bbox.y_max)
                helper.draw_rectangle(
                    top_left=tl,
                    bottom_right=br,
                    outline_color=annot_color,
                    fill_color=None,
                    thickness=2,
                )
                bbox_label_pos = (tl[0], max(0.02, tl[1] - 0.02))
                helper.draw_text(
                    text=f"{obj.id}. | z-distance: {obj.nearest_point_depth / 1000:.1f}m",
                    position=bbox_label_pos,
                    color=annot_color,
                    size=16,
                    background_color=dai.Color(0.0, 0.0, 0.0, 0.45),
                )

        return helper.build(timestamp=timestamp, sequence_num=sequence_num)

    def _zone_of_obstacle(self, obstacle) -> DangerLevel:
        return classify_obstacle(
            obstacle=obstacle,
            danger_zone=self._danger_zone,
            warning_zone=self._warning_zone,
        )

    def _zone_color(self, zone: DangerLevel) -> tuple[int, int, int]:
        if zone is DangerLevel.DANGER:
            return self.COLOR_DANGER
        if zone is DangerLevel.WARNING:
            return self.COLOR_WARNING
        return self.COLOR_SAFE

    @staticmethod
    def _bgr_to_color(bgr, alpha=1.0):
        b, g, r = bgr
        return dai.Color(r / 255.0, g / 255.0, b / 255.0, alpha)
