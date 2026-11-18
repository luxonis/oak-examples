from typing import Optional, Tuple

import numpy as np

# The ground is searched among planes whose normal is within this angle of the
# vertical (Y) axis of the calibration origin camera.
MAX_TILT_DEG = 45.0
INLIER_DISTANCE_M = 0.03
ITERATIONS = 500
MAX_POINTS = 30000


def fit_ground_plane(
    points: np.ndarray, seed: int = 0
) -> Optional[Tuple[np.ndarray, np.ndarray, float]]:
    """Fit the ground plane to an Nx3 point cloud in meters with RANSAC.

    Returns (point on the plane, unit normal pointing towards the cameras, inlier ratio),
    or None when no roughly horizontal plane is found.
    """
    points = points[np.isfinite(points).all(axis=1)]
    points = points[np.linalg.norm(points, axis=1) > 0.1]
    if len(points) < 100:
        return None

    rng = np.random.default_rng(seed)
    if len(points) > MAX_POINTS:
        points = points[rng.choice(len(points), MAX_POINTS, replace=False)]

    min_vertical = np.cos(np.radians(MAX_TILT_DEG))
    best_inliers = None
    for _ in range(ITERATIONS):
        a, b, c = points[rng.choice(len(points), 3, replace=False)]
        normal = np.cross(b - a, c - a)
        length = np.linalg.norm(normal)
        if length < 1e-9:
            continue
        normal /= length
        # Camera Y points down, so the ground normal is close to the Y axis.
        if abs(normal[1]) < min_vertical:
            continue
        inliers = np.abs((points - a) @ normal) < INLIER_DISTANCE_M
        if best_inliers is None or inliers.sum() > best_inliers.sum():
            best_inliers = inliers

    if best_inliers is None or best_inliers.sum() < 100:
        return None

    # Least-squares refinement on the inliers: the normal is the direction of least variance.
    ground = points[best_inliers]
    centroid = ground.mean(axis=0)
    normal = np.linalg.svd(ground - centroid, full_matrices=False)[2][-1]
    # Point the normal from the ground towards the origin camera.
    if normal @ (-centroid) < 0:
        normal = -normal
    return centroid, normal, float(best_inliers.mean())
