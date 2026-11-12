import logging

import numpy as np
import open3d as o3d

from solutions_sdk.box_measurement.helper.plane_validation import (
    is_valid_horizontal_plane,
)
from solutions_sdk.box_measurement.message.calibration import PlaneCalibrationConfig
from solutions_sdk.box_measurement.message.support_plane import SupportPlane

logger = logging.getLogger(__name__)


class SupportPlaneFitter:
    """Finds horizontal plane candidates in an organized point cloud."""

    def __init__(
        self, pcl_shape: tuple[int, int], config: PlaneCalibrationConfig
    ) -> None:
        self._width, self._height = pcl_shape
        self._config = config

    @property
    def shape(self) -> tuple[int, int]:
        """Organized cloud shape as ``(width, height)``."""
        return self._width, self._height

    @property
    def expected_point_count(self) -> int:
        """Number of points an organized cloud of this shape must have."""
        return self._width * self._height

    def find_candidates(
        self,
        points: np.ndarray,
        g: np.ndarray,
    ) -> list[SupportPlane]:
        """Finds horizontal plane candidates and returns them best first."""
        self._validate_point_cloud_shape(points)

        point_cloud = self._preprocess_point_cloud(points)
        if point_cloud is None:
            return []

        plane_candidates = self._fit_plane_candidates(point_cloud, g)
        if not plane_candidates:
            logger.debug("RANSAC rejected: no horizontal plane candidates")
            return []

        plane_candidates = self._drop_duplicate_planes(plane_candidates)
        return self._rank_plane_candidates(plane_candidates)

    def _validate_point_cloud_shape(self, points: np.ndarray) -> None:
        """Validates the organized point cloud shape."""
        expected = (self.expected_point_count, 3)
        if points.shape != expected:
            raise ValueError(
                f"Point cloud is not organized to {self.shape}: "
                f"got shape {points.shape}, expected {expected}"
            )

    def _preprocess_point_cloud(
        self, points: np.ndarray
    ) -> o3d.geometry.PointCloud | None:
        """Filters the point cloud before plane fitting."""
        valid = points[:, 2] > 1e-6
        points = points[valid]

        pcl = o3d.geometry.PointCloud()
        pcl.points = o3d.utility.Vector3dVector(points.astype(np.float64))
        pcl = pcl.voxel_down_sample(voxel_size=self._config.voxel_size_mm)
        pcl, _ = pcl.remove_statistical_outlier(20, 0.1)

        if len(pcl.points) < self._config.ransac_sample_points:
            logger.debug(
                "RANSAC rejected: not enough points after filtering "
                "(got %d, need at least %d)",
                len(pcl.points),
                self._config.ransac_sample_points,
            )
            return None

        return pcl

    def _fit_plane_candidates(
        self,
        pcl: o3d.geometry.PointCloud,
        g: np.ndarray,
    ) -> list[tuple[int, np.ndarray, np.ndarray]]:
        """Finds horizontal planes using multiple RANSAC passes."""
        min_inliers = max(
            self._config.ransac_sample_points,
            int(self._config.min_inlier_ratio * len(pcl.points)),
        )
        candidates: list[tuple[int, np.ndarray, np.ndarray]] = []

        for _ in range(self._config.max_plane_passes):
            if len(pcl.points) < min_inliers:
                break

            try:
                plane_eq, inliers = pcl.segment_plane(
                    self._config.distance_threshold_mm,
                    self._config.ransac_sample_points,
                    self._config.ransac_max_iterations,
                )
            except RuntimeError as exc:
                logger.debug("RANSAC failed during plane segmentation: %s", exc)
                break

            if len(inliers) < min_inliers:
                logger.debug(
                    "RANSAC rejected: too few inliers (got %d, need at least %d)",
                    len(inliers),
                    min_inliers,
                )
                break

            plane_eq = np.asarray(plane_eq, dtype=np.float32)
            norm = float(np.linalg.norm(plane_eq[:3]))
            if norm < 1e-6:
                break
            plane_eq /= norm

            if is_valid_horizontal_plane(
                plane_eq, g, self._config.max_gravity_angle_deg
            ):
                centroid = np.asarray(pcl.points)[inliers].mean(axis=0)
                candidates.append((len(inliers), plane_eq, centroid))

            pcl = pcl.select_by_index(inliers, invert=True)

        return candidates

    def _drop_duplicate_planes(
        self, plane_candidates: list[tuple[int, np.ndarray, np.ndarray]]
    ) -> list[tuple[int, np.ndarray, np.ndarray]]:
        """Keeps one plane per surface, preferring the one with most inliers.

        Noisy depth can make RANSAC split one surface into near-parallel planes.
        """
        unique: list[tuple[int, np.ndarray, np.ndarray]] = []
        for candidate in sorted(plane_candidates, key=lambda c: -c[0]):
            _, plane_eq, centroid = candidate
            if any(
                self._is_same_surface(plane_eq, centroid, kept_eq, kept_centroid)
                for _, kept_eq, kept_centroid in unique
            ):
                logger.debug(
                    "Plane candidate dropped as duplicate (offset=%.2f)", plane_eq[3]
                )
                continue
            unique.append(candidate)
        return unique

    def _is_same_surface(
        self,
        eq_a: np.ndarray,
        centroid_a: np.ndarray,
        eq_b: np.ndarray,
        centroid_b: np.ndarray,
    ) -> bool:
        """Checks if two planes are close at each other's inlier centroids.
        Noisy depth can make RANSAC split one surface into near-parallel planes.
        """
        dist_ab = abs(float(np.dot(eq_a[:3], centroid_b) + eq_a[3]))
        dist_ba = abs(float(np.dot(eq_b[:3], centroid_a) + eq_b[3]))
        return max(dist_ab, dist_ba) < self._config.merge_distance_threshold_mm

    def _rank_plane_candidates(
        self, plane_candidates: list[tuple[int, np.ndarray, np.ndarray]]
    ) -> list[SupportPlane]:
        """Orders by inlier count, then by proximity to the camera."""
        ranked = sorted(plane_candidates, key=lambda c: (-c[0], abs(c[1][3])))
        return [
            SupportPlane(
                normal=(float(equation[0]), float(equation[1]), float(equation[2])),
                offset_mm=float(equation[3]),
            )
            for _, equation, _ in ranked
        ]
