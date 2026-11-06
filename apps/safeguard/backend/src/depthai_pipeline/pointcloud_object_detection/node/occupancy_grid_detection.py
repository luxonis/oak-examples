from dataclasses import dataclass

import cv2
import depthai as dai
import numpy as np

from util.ground_alignment import ground_to_camera

from ..message import BoundingBox, Obstacle, Obstacles, OccupancyMask, PlaneValidity


@dataclass(frozen=True)
class BinnedPoints:
    """Ground-frame points with matching angle and range bin indices.

    Each array uses the same index for a point and its two polar-grid cells.
    """

    valid_points: np.ndarray
    angle_bin_indices: np.ndarray
    range_bin_indices: np.ndarray


class OccupancyGridDetectionNode(dai.node.HostNode):
    """Bin obstacle points into a polar grid and extract obstacle components.

    Publishes normalized image boxes and nearest points for each component,
    plus a binary occupancy mask. Incoming points use ground-frame millimeters.
    """

    # Grid resolution
    RANGE_RES = 100  # mm
    ANGLE_RES = 2.0  # deg
    MAX_RANGE = 9000  # mm
    MIN_VISIBLE_RANGE = 200  # mm

    # Detection thresholds
    MIN_OBSTACLE_PTS = 25
    MIN_OBSTACLE_CELLS = 3

    def __init__(self, hfov_deg: float = 67.3):
        super().__init__()
        self.out_obstacles = self.createOutput()
        self.out_occupancy_mask = self.createOutput()

        self._intrinsics: tuple[float, float, float, float] | None = (
            None  # (fx, fy, cx, cy)
        )
        self._frame_size: tuple[int, int] | None = None  # (w, h)
        # cam->ground rotation for the current frame; set in process()
        self._R: np.ndarray | None = None

        self._initialize_grid(hfov_deg)

    def build(
        self,
        obstacle_pcl: dai.Node.Output,
        plane_valid: dai.Node.Output,
        intrinsics: tuple[float, float, float, float],
        frame_size: tuple[int, int],
    ) -> "OccupancyGridDetectionNode":
        self._intrinsics = intrinsics
        self._frame_size = frame_size

        self.link_args(obstacle_pcl, plane_valid)
        return self

    def process(
        self,
        obstacle_msg: dai.Buffer,
        plane_valid_msg: dai.Buffer,
    ) -> None:
        try:
            assert isinstance(obstacle_msg, dai.PointCloudData)
            assert isinstance(plane_valid_msg, PlaneValidity)

            obstacle_pts = obstacle_msg.getPoints()
            plane_valid = bool(plane_valid_msg.plane_valid)
            self._R = (
                np.asarray(plane_valid_msg.R, dtype=np.float32)
                if plane_valid and plane_valid_msg.R.size == 9
                else None
            )

            if plane_valid:
                obstacle_binned = self._bin_points_to_grid(obstacle_pts)
                self._build_count_grid(obstacle_binned)
                occupancy_mask = self._compute_occupancy_mask()
                obstacles = self._detect_obstacles(occupancy_mask, obstacle_binned)
            else:
                self._obstacle_count[:] = 0
                occupancy_mask = np.zeros(
                    (self._n_range_bins, self._n_angle_bins), dtype=bool
                )
                obstacles = []

            obstacles_msg = Obstacles(obstacles=obstacles)
            obstacles_msg.setTimestamp(obstacle_msg.getTimestamp())
            obstacles_msg.setSequenceNum(obstacle_msg.getSequenceNum())
            self.out_obstacles.send(obstacles_msg)

            occupancy_mask_msg = OccupancyMask(mask=occupancy_mask)
            occupancy_mask_msg.setTimestamp(obstacle_msg.getTimestamp())
            occupancy_mask_msg.setSequenceNum(obstacle_msg.getSequenceNum())
            self.out_occupancy_mask.send(occupancy_mask_msg)
        except dai.MessageQueue.QueueException:
            return

    def _initialize_grid(self, hfov_deg: float) -> None:
        self._half_fov_rad = np.radians(hfov_deg / 2.0)
        self._angle_bin_rad = np.radians(self.ANGLE_RES)
        self._n_angle_bins = int(
            np.ceil((2.0 * self._half_fov_rad) / self._angle_bin_rad)
        )
        self._n_range_bins = int(np.ceil(self.MAX_RANGE / self.RANGE_RES))

        self._min_range_sq = float(self.MIN_VISIBLE_RANGE) ** 2
        self._max_range_sq = float(self._n_range_bins * self.RANGE_RES) ** 2

        self._obstacle_count = np.zeros(
            (self._n_range_bins, self._n_angle_bins), dtype=np.int32
        )

    def _bin_points_to_grid(self, points: np.ndarray) -> BinnedPoints:
        """Map ground-frame 3D points to horizontal angle and planar range bins.

        Args:
            points: Nx3 points in millimeters.

        Returns:
            In-range points and their aligned grid indices.
        """
        empty = BinnedPoints(
            valid_points=np.empty((0, 3), dtype=np.float32),
            angle_bin_indices=np.empty((0,), dtype=np.int32),
            range_bin_indices=np.empty((0,), dtype=np.int32),
        )
        if points.shape[0] == 0:
            return empty

        x = points[:, 0]
        z = points[:, 2]
        planar_range_sq = x * x + z * z
        in_range = (planar_range_sq >= self._min_range_sq) & (
            planar_range_sq < self._max_range_sq
        )
        if not np.any(in_range):
            return empty

        kept = points[in_range]
        planar_range_mm = np.sqrt(planar_range_sq[in_range])
        horizontal_angle_rad = np.arctan2(kept[:, 0], kept[:, 2])

        angle_bin_coords = (
            horizontal_angle_rad + self._half_fov_rad
        ) / self._angle_bin_rad
        range_bin_coords = planar_range_mm / self.RANGE_RES

        in_fov = (angle_bin_coords >= 0) & (angle_bin_coords < self._n_angle_bins)

        return BinnedPoints(
            valid_points=kept[in_fov],
            angle_bin_indices=np.floor(angle_bin_coords[in_fov]).astype(np.int32),
            range_bin_indices=np.floor(range_bin_coords[in_fov]).astype(np.int32),
        )

    def _build_count_grid(self, binned_points: BinnedPoints) -> None:
        """Count obstacle points in each polar grid cell."""
        self._obstacle_count[:] = 0

        self._fill_count_grid(binned_points, self._obstacle_count)

    def _fill_count_grid(self, binned: BinnedPoints, count_grid: np.ndarray) -> None:
        if binned.valid_points.shape[0] == 0:
            return

        flat_bin_indices = (
            binned.range_bin_indices * self._n_angle_bins + binned.angle_bin_indices
        )
        flat_bin_counts = np.bincount(flat_bin_indices, minlength=count_grid.size)
        count_grid[:] = flat_bin_counts.reshape(count_grid.shape)

    def _compute_occupancy_mask(self) -> np.ndarray:
        """Mark cells occupied when their point count reaches the threshold."""
        return self._obstacle_count >= self.MIN_OBSTACLE_PTS

    def _detect_obstacles(
        self,
        occupancy_mask: np.ndarray,
        binned_obstacle_points: BinnedPoints,
    ) -> list[Obstacle]:
        """Group occupied cells into components and derive obstacle geometry."""
        occupancy_mask_u8 = occupancy_mask.astype(np.uint8)
        # Connect occupied cells to form obstacle blobs
        _, label_grid, stats, _ = cv2.connectedComponentsWithStats(
            occupancy_mask_u8,
            connectivity=4,
        )

        # Filter components by occupied-cell count
        valid_component = stats[:, cv2.CC_STAT_AREA] >= self.MIN_OBSTACLE_CELLS
        valid_component[0] = False  # background
        # Remap too-small components to background so their points are dropped early.
        label_grid = np.where(valid_component[label_grid], label_grid, 0)

        points_by_obstacle = self._group_points_by_label(
            label_grid,
            binned_obstacle_points,
        )

        obstacles: list[Obstacle] = []
        for label_id, obstacle_points in points_by_obstacle.items():
            uv_norm = self._project_points_normalized(obstacle_points)
            bbox = self._bbox_from_normalized(uv_norm)
            if bbox is None:
                continue

            nearest_xyz, nearest_depth_mm, nearest_radial_mm = self._find_nearest_point(
                obstacle_points
            )
            obstacles.append(
                Obstacle(
                    id=0,
                    bbox=bbox,
                    nearest_point_xyz=nearest_xyz,
                    nearest_point_depth=nearest_depth_mm,
                    nearest_point_radial=nearest_radial_mm,
                )
            )

        # Sort obstacles by distance from nearest
        obstacles.sort(key=lambda obj: obj.nearest_point_depth)
        for idx, obstacle in enumerate(obstacles):
            obstacle.id = idx

        return obstacles

    def _project_points_normalized(self, points: np.ndarray) -> np.ndarray:
        """Project ground-frame points into normalized image coordinates."""
        if self._intrinsics is None or self._frame_size is None:
            raise ValueError(
                "Projection parameters not set. Ensure build() has been called."
            )
        if self._R is None:
            return np.empty((0, 2), dtype=np.float32)

        fx, fy, cx, cy = self._intrinsics
        img_w, img_h = self._frame_size

        points = np.atleast_2d(points)
        # Incoming points are ground-frame; pinhole projection needs camera-frame
        points_cam = ground_to_camera(points, self._R)
        z = points_cam[:, 2]
        valid = z > 1e-6
        if not np.any(valid):
            return np.empty((0, 2), dtype=np.float32)

        pts = points_cam[valid]
        u = (fx * pts[:, 0] / pts[:, 2] + cx) / img_w
        v = (fy * pts[:, 1] / pts[:, 2] + cy) / img_h

        in_bounds = (u >= 0) & (u < 1) & (v >= 0) & (v < 1)
        if not np.any(in_bounds):
            return np.empty((0, 2), dtype=np.float32)

        return np.column_stack((u[in_bounds], v[in_bounds])).astype(np.float32)

    @staticmethod
    def _bbox_from_normalized(
        uv_norm: np.ndarray, min_projected_points: int = 8
    ) -> BoundingBox | None:
        if uv_norm.shape[0] < min_projected_points:
            return None

        x0 = float(uv_norm[:, 0].min())
        y0 = float(uv_norm[:, 1].min())
        x1 = float(uv_norm[:, 0].max())
        y1 = float(uv_norm[:, 1].max())

        return BoundingBox(x_min=x0, y_min=y0, x_max=x1, y_max=y1)

    @staticmethod
    def _find_nearest_point(
        component_points: np.ndarray,
    ) -> tuple[np.ndarray, float, float]:
        """Return the nearest point by forward depth and its planar range."""
        idx_z = int(np.argmin(component_points[:, 2]))
        nearest_xyz = component_points[idx_z]

        min_depth_mm = float(nearest_xyz[2])  # z-distance from camera to point
        min_range_mm = float(
            np.hypot(nearest_xyz[0], nearest_xyz[2])
        )  # radial distance from camera to point
        return nearest_xyz, min_depth_mm, min_range_mm

    @staticmethod
    def _group_points_by_label(
        label_grid: np.ndarray,
        binned: BinnedPoints,
    ) -> dict[int, np.ndarray]:
        """Group binned obstacle points by connected-component label. Label 0 is background."""
        if binned.valid_points.shape[0] == 0:
            return {}

        # Look up which obstacle (connected component) each point belongs to
        point_labels = label_grid[binned.range_bin_indices, binned.angle_bin_indices]
        foreground = point_labels > 0
        if not np.any(foreground):
            return {}

        labels = point_labels[foreground]
        points = binned.valid_points[foreground]

        # Sort once by label, then split on boundaries
        sort_order = np.argsort(labels, kind="stable")
        sorted_labels = labels[sort_order]
        sorted_points = points[sort_order]

        component_boundary_indices = np.flatnonzero(np.diff(sorted_labels)) + 1
        point_groups = np.split(sorted_points, component_boundary_indices)
        group_ids = sorted_labels[np.concatenate(([0], component_boundary_indices))]

        return {int(lid): grp for lid, grp in zip(group_ids, point_groups)}
