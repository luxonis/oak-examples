import logging

import cv2
import numpy as np
import open3d as o3d

from solutions_sdk.box_measurement.message.box_measurements import BoxDimensions

logger = logging.getLogger(__name__)


class BoxMeasurement:
    """Measures box dimensions from a point cloud."""

    MIN_POINTS = 50
    VOXEL_SIZE = 3.0
    MAD_K = 3.0
    HEIGHT_PERCENTILE = 98.0

    # Length/width parameters
    MIN_FOOTPRINT_POINTS = 30
    MAX_HEIGHT_MARGIN_MM = 20.0
    TOP_BAND_FRACTION = 0.85

    # Top-plane fit parameters
    TOP_PLANE_BAND_FRACTION = 0.80
    TOP_PLANE_RANSAC_THRESH_MM = 5.0
    TOP_PLANE_ITERATIONS = 50
    MIN_TOP_PLANE_POINTS = 20

    def measure(self, points: np.ndarray, plane_eq: np.ndarray) -> BoxDimensions | None:
        if points.shape[0] < self.MIN_POINTS:
            return None

        filtered = self._filter_points(points)
        if filtered.shape[0] < self.MIN_POINTS:
            return None

        plane_eq = self._normalized_plane(plane_eq)

        height_mm = self._height(filtered, plane_eq)
        if height_mm is None:
            return None

        length_width = self._length_width(filtered, plane_eq, height_mm)
        if length_width is None:
            return None

        length_mm, width_mm = length_width

        return BoxDimensions(
            height_mm=height_mm,
            length_mm=length_mm,
            width_mm=width_mm,
        )

    # --- filtering -----------------------------------------------------------

    def _filter_points(self, points: np.ndarray) -> np.ndarray:
        """Downsamples and filters the point cloud."""
        pcl = o3d.geometry.PointCloud()
        pcl.points = o3d.utility.Vector3dVector(points.astype(np.float64))
        pcl = pcl.voxel_down_sample(voxel_size=self.VOXEL_SIZE)
        pcl, _ = pcl.remove_statistical_outlier(10, 0.2)
        return np.asarray(pcl.points)

    def _mad_inliers(self, points: np.ndarray) -> np.ndarray:
        """Median-absolute-deviation filtering."""
        if points.shape[0] == 0:
            return np.empty(0, dtype=int)

        median_point = np.median(points, axis=0)
        distances = np.linalg.norm(points - median_point, axis=1)
        median_distance = np.median(distances)
        mad = np.median(np.abs(distances - median_distance))

        if mad == 0:
            mask = np.ones_like(distances, dtype=bool)
        else:
            mask = np.abs(distances - median_distance) < self.MAD_K * mad

        return np.flatnonzero(mask)

    # --- height --------------------------------------------------------------

    def _height(self, points: np.ndarray, plane_eq: np.ndarray) -> float | None:
        idx = self._mad_inliers(points)
        pts = points[idx] if idx.size else points

        # Distance of every box point to the support plane; isolate the top band
        distances = np.abs(pts @ plane_eq[:3] + plane_eq[3])
        top = float(np.percentile(distances, self.HEIGHT_PERCENTILE))
        top_band_distances = distances[distances > self.TOP_PLANE_BAND_FRACTION * top]
        return self._estimate_top_height(top_band_distances)

    def _estimate_top_height(self, top_band_distances: np.ndarray) -> float | None:
        """Estimates the dominant height in the top band."""
        if top_band_distances.size < self.MIN_TOP_PLANE_POINTS:
            return None

        rng = np.random.default_rng(0)
        best_inliers = np.empty(0, dtype=int)

        for _ in range(self.TOP_PLANE_ITERATIONS):
            level = top_band_distances[rng.integers(0, top_band_distances.size)]
            inliers = np.flatnonzero(
                np.abs(top_band_distances - level) <= self.TOP_PLANE_RANSAC_THRESH_MM
            )

            if inliers.size > best_inliers.size:
                best_inliers = inliers

        if best_inliers.size < self.MIN_TOP_PLANE_POINTS:
            return None
        return float(np.mean(top_band_distances[best_inliers]))

    # --- length / width ------------------------------------------------------

    def _length_width(
        self,
        points: np.ndarray,
        plane_eq: np.ndarray,
        height_mm: float,
    ) -> tuple[float, float] | None:
        """Project the top band of box points onto the support plane and fit a
        2D min-area rectangle."""
        xy, signed_height = self._to_plane_coords(points, plane_eq)

        finite = np.isfinite(xy).all(axis=1) & np.isfinite(signed_height)

        lower_height = self.TOP_BAND_FRACTION * height_mm
        upper_height = height_mm + self.MAX_HEIGHT_MARGIN_MM

        valid = finite & (signed_height > lower_height) & (signed_height < upper_height)
        xy_used = xy[valid]
        n_footprint = int(xy_used.shape[0])
        if n_footprint < self.MIN_FOOTPRINT_POINTS:
            logger.debug(
                "footprint too small: %d pts (< %d)",
                n_footprint,
                self.MIN_FOOTPRINT_POINTS,
            )
            return None

        rect = cv2.minAreaRect(xy_used.astype(np.float32))
        side_a, side_b = rect[1]
        if side_a <= 1e-6 or side_b <= 1e-6:
            logger.debug(
                "degenerate footprint: %d pts, sides=(%.2f, %.2f) mm",
                n_footprint,
                side_a,
                side_b,
            )
            return None

        length_mm = float(max(side_a, side_b))
        width_mm = float(min(side_a, side_b))
        return length_mm, width_mm

    # --- support-plane frame -------------------------------------------------

    @staticmethod
    def _normalized_plane(plane_eq: np.ndarray) -> np.ndarray:
        plane_eq = np.asarray(plane_eq, dtype=np.float64).reshape(-1)
        norm = np.linalg.norm(plane_eq[:3])
        if norm < 1e-9:
            raise ValueError(f"Invalid plane normal: {plane_eq[:3]}")
        return plane_eq / norm

    def _plane_frame(
        self, plane_eq: np.ndarray, reference_points: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Builds a coordinate frame aligned with the support plane."""
        normal = plane_eq[:3].copy()
        d = float(plane_eq[3])

        if reference_points.shape[0] > 0:
            signed = reference_points @ normal + d
            signed = signed[np.isfinite(signed)]
            if signed.size > 0 and np.median(signed) < 0:
                normal = -normal
                d = -d

        origin = -d * normal

        ref = np.array([0.0, 0.0, 1.0])
        if abs(np.dot(normal, ref)) > 0.95:
            ref = np.array([0.0, 1.0, 0.0])

        u = np.cross(normal, ref)
        u /= np.linalg.norm(u) + 1e-12
        v = np.cross(normal, u)
        v /= np.linalg.norm(v) + 1e-12

        return origin, normal, u, v

    def _to_plane_coords(
        self, points: np.ndarray, plane_eq: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        """Returns 2D in-plane (u, v) coords and signed height above the plane."""
        origin, normal, u, v = self._plane_frame(plane_eq, points)

        # origin = -d * normal, so (p - origin) . normal == p . normal + d, but
        # using origin keeps it consistent with the (possibly flipped) frame.
        signed_height = (points - origin) @ normal

        rel = points - signed_height[:, None] * normal - origin
        xy = np.column_stack([rel @ u, rel @ v]).astype(np.float32)
        return xy, signed_height.astype(np.float32)
