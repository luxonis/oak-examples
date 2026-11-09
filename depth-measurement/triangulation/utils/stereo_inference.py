import numpy as np


class StereoInference:
    """Rectified-left XYZ in millimeters: X right, Y down, Z forward."""

    def __init__(self, baseline_mm: float) -> None:
        if not np.isfinite(baseline_mm) or baseline_mm <= 0:
            raise ValueError("A positive calibrated stereo baseline is required")
        self.baseline_mm = baseline_mm

    def triangulate(
        self, left, right, intrinsics, min_disparity=0.5, max_vertical_error=3.0
    ):
        """Only accept corresponding points in a synchronized rectified pair."""
        values = np.asarray([*left, *right], dtype=float)
        if not np.all(np.isfinite(values)):
            return None
        disparity = left[0] - right[0]
        if disparity <= min_disparity or abs(left[1] - right[1]) > max_vertical_error:
            return None
        k = np.asarray(intrinsics)
        fx, fy, cx, cy = k[0, 0], k[1, 1], k[0, 2], k[1, 2]
        if not np.all(np.isfinite(k)) or fx <= 0 or fy <= 0:
            raise ValueError("Rectified frame must provide valid intrinsics")
        z = self.baseline_mm * fx / disparity
        return [(left[0] - cx) * z / fx, (left[1] - cy) * z / fy, z]
