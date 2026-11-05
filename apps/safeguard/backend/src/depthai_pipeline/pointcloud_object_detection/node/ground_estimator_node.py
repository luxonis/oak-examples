import logging
from typing import cast

import depthai as dai
import numpy as np
import open3d as o3d

from settings.settings import GroundRefitMode
from util.ground_alignment import rotation_from_imu, camera_to_ground
from ..message import PlaneValidity

logger = logging.getLogger(__name__)


class GroundEstimatorNode(dai.node.ThreadedHostNode):
    """Fit an IMU-validated ground plane and publish ground-aligned obstacles.

    DYNAMIC mode periodically refits the plane. STATIC mode caches a valid
    plane until measured gravity drifts, suggesting camera movement. Distances
    and point coordinates are in millimeters.
    """

    REFIT_INTERVAL_FRAMES = 5

    # RANSAC parameters (mm)
    DISTANCE_THR = 20.0
    SAMPLE_POINTS = 3
    MAX_ITERATIONS = 300
    DOWNSAMPLE_FACTOR = 7
    INLIER_RATIO_THR = 0.1
    VOXEL_SIZE = 30

    # IMU validation
    GRAVITY_ANGLE_THR = 10.0  # max degrees between plane normal and gravity
    DRIFT_ANGLE_THR = 4.0  # re-estimate if gravity drifted more than this

    # Classification
    GROUND_DIST_THR = 45  # mm, max distance from plane to count as ground

    def __init__(self):
        super().__init__()
        self.out_obstacle = self.createOutput()
        self.out_plane_valid = self.createOutput()

        self._input_pcl = self.createInput()
        self._input_imu = self.createInput()

        self._refit_mode = GroundRefitMode.STATIC

        # Cached plane state
        self.plane_eq: np.ndarray | None = None
        self.gravity_dir_at_estimate: np.ndarray | None = (
            None  # normalized gravity when plane was estimated
        )
        self._R: np.ndarray | None = None  # cam -> ground rotation, refreshed on refit

        self._pcl = o3d.geometry.PointCloud()

        self._frames_since_fit_attempt = self.REFIT_INTERVAL_FRAMES

    def build(
        self,
        pcl: dai.Node.Output,
        imu: dai.Node.Output,
        refit_mode: GroundRefitMode,
    ) -> "GroundEstimatorNode":
        """Connect point cloud and IMU streams and select the refit policy."""
        pcl.link(self._input_pcl)
        imu.link(self._input_imu)

        self._refit_mode = refit_mode
        return self

    def run(self) -> None:
        latest_imu: dai.IMUData | None = None

        while self.isRunning():
            pcl_msg = self._input_pcl.get()

            while True:
                new_imu = self._input_imu.tryGet()
                if new_imu is None:
                    break
                latest_imu = cast(dai.IMUData, new_imu)

            self._process_pcl(pcl_msg, latest_imu)

    def _process_pcl(
        self,
        pcl_msg: dai.PointCloudData,
        imu_msg: dai.IMUData | None,
    ) -> None:
        """Filter ground points, publishing an empty cloud when no plane is valid."""
        if imu_msg is None:
            self._publish_empty_clouds(pcl_msg)
            self._publish_plane_valid(pcl_msg, False, None, None)
            return

        g = self._extract_gravity_vector(imu_msg)
        if g is None:
            self._publish_empty_clouds(pcl_msg)
            self._publish_plane_valid(
                pcl_msg, self.plane_eq is not None, self.plane_eq, self._R
            )
            return

        points, colors = pcl_msg.getPointsRGB()

        if len(points) == 0:
            self._publish_empty_clouds(pcl_msg)
            self._publish_plane_valid(
                pcl_msg, self.plane_eq is not None, self.plane_eq, self._R
            )
            return

        points = points[:: self.DOWNSAMPLE_FACTOR]
        colors = colors[:: self.DOWNSAMPLE_FACTOR]

        valid_mask = points[:, 2] > 1e-6
        if not np.any(valid_mask):
            self._publish_empty_clouds(pcl_msg)
            self._publish_plane_valid(
                pcl_msg, self.plane_eq is not None, self.plane_eq, self._R
            )
            return

        if self._should_attempt_fit(g):
            ok = self._fit_plane(points[valid_mask], g)
            if not ok:
                self.plane_eq = None
                self.gravity_dir_at_estimate = None
                self._R = None

        if self.plane_eq is None or self._R is None:
            self._publish_empty_clouds(pcl_msg)
            self._publish_plane_valid(pcl_msg, False, None, None)
            return

        plane = self.plane_eq

        # plane_eq is normalized at fit time -> |a*x + b*y + c*z + d| is the perpendicular distance.
        signed_dist = (
            points[:, 0] * plane[0]
            + points[:, 1] * plane[1]
            + points[:, 2] * plane[2]
            + plane[3]
        )

        obstacle_mask = valid_mask & (np.abs(signed_dist) >= self.GROUND_DIST_THR)

        obstacle_points = points[obstacle_mask]
        colors_obstacle = colors[obstacle_mask]

        obstacle_points = camera_to_ground(obstacle_points, self._R)
        obstacle_msg = dai.PointCloudData()
        obstacle_msg.setPointsRGB(obstacle_points, colors_obstacle)
        obstacle_msg.setTimestamp(pcl_msg.getTimestamp())
        obstacle_msg.setSequenceNum(pcl_msg.getSequenceNum())

        self.out_obstacle.send(obstacle_msg)
        self._publish_plane_valid(pcl_msg, True, self.plane_eq, self._R)

    def _extract_gravity_vector(self, imu_msg: dai.IMUData) -> np.ndarray | None:
        """Get gravity vector from IMU accelerometer data."""
        for pkt in imu_msg.packets:
            if hasattr(pkt, "acceleroMeter") and pkt.acceleroMeter is not None:
                a = pkt.acceleroMeter
                return np.array([a.x, a.y, a.z], dtype=np.float32)
        return None

    def _should_attempt_fit(self, g: np.ndarray) -> bool:
        """Check if this frame should attempt ground plane fitting."""
        if self._refit_mode == GroundRefitMode.DYNAMIC:
            return self._is_fit_frame()

        if self.plane_eq is None:
            return self._is_fit_frame()

        return self._gravity_drift_detected(g)

    def _is_fit_frame(self) -> bool:
        self._frames_since_fit_attempt += 1

        if self._frames_since_fit_attempt < self.REFIT_INTERVAL_FRAMES:
            return False

        self._frames_since_fit_attempt = 0
        return True

    def _gravity_drift_detected(self, g: np.ndarray) -> bool:
        """Check if gravity vector has drifted."""
        if self.gravity_dir_at_estimate is None:
            return True

        g_n = g / (np.linalg.norm(g) + 1e-9)
        cos_a = np.clip(np.dot(self.gravity_dir_at_estimate, g_n), -1.0, 1.0)
        if cos_a < np.cos(np.deg2rad(self.DRIFT_ANGLE_THR)):
            return True

        return False

    def _fit_plane(self, points: np.ndarray, g: np.ndarray) -> bool:
        """Fit a plane with RANSAC and reject candidates inconsistent with gravity.

        Args:
            points: Camera-frame 3D points in millimeters.
            g: IMU gravity vector in camera coordinates.

        Returns:
            True if a valid plane and ground rotation were cached.
        """
        pts = points.astype(np.float64)
        self._pcl.points = o3d.utility.Vector3dVector(pts)

        pcl = self._pcl.voxel_down_sample(voxel_size=self.VOXEL_SIZE)

        if len(pcl.points) < self.SAMPLE_POINTS:
            return False

        try:
            plane_eq, inliers = pcl.segment_plane(
                self.DISTANCE_THR, self.SAMPLE_POINTS, self.MAX_ITERATIONS
            )
        except RuntimeError:
            return False

        inlier_ratio = len(inliers) / len(pcl.points)
        if inlier_ratio < self.INLIER_RATIO_THR:
            logger.debug(
                "RANSAC failed: inlier ratio %.3f below threshold", inlier_ratio
            )
            return False

        plane_eq = np.asarray(plane_eq, dtype=np.float32)
        norm = float(np.linalg.norm(plane_eq[:3]))
        if norm < 1e-6:
            return False
        plane_eq /= norm

        n_n = plane_eq[:3]
        g_n = (g / (np.linalg.norm(g) + 1e-9)).astype(np.float32)
        if (
            np.dot(n_n, g_n) > -np.cos(np.deg2rad(self.GRAVITY_ANGLE_THR))
            or plane_eq[3] > 0
        ):
            return False

        R = rotation_from_imu(g)
        if R is None:
            return False

        self.plane_eq = plane_eq
        self.gravity_dir_at_estimate = g_n
        self._R = R
        return True

    def _publish_empty_clouds(self, pcl_msg: dai.PointCloudData) -> None:
        empty_points = np.empty((0, 3), dtype=np.float32)
        obstacle_msg = dai.PointCloudData()
        obstacle_msg.setPoints(empty_points)
        obstacle_msg.setTimestamp(pcl_msg.getTimestamp())
        obstacle_msg.setSequenceNum(pcl_msg.getSequenceNum())
        self.out_obstacle.send(obstacle_msg)

    def _publish_plane_valid(
        self,
        pcl_msg: dai.PointCloudData,
        plane_valid: bool,
        plane_eq: np.ndarray | None,
        R: np.ndarray | None,
    ) -> None:
        plane_valid_msg = PlaneValidity(plane_valid=plane_valid, plane_eq=plane_eq, R=R)
        plane_valid_msg.setTimestamp(pcl_msg.getTimestamp())
        plane_valid_msg.setSequenceNum(pcl_msg.getSequenceNum())
        self.out_plane_valid.send(plane_valid_msg)
