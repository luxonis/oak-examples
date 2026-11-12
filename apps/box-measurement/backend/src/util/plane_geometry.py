import numpy as np


def camera_tilt_deg(plane_eq: np.ndarray) -> float:
    """Angle between the optical axis and the plane normal; 0 = looking straight down."""
    normal = plane_eq[:3]
    cos_tilt = min(1.0, abs(float(normal[2])) / float(np.linalg.norm(normal)))
    return float(np.degrees(np.arccos(cos_tilt)))


def camera_distance_mm(plane_eq: np.ndarray) -> float | None:
    """Distance from the camera to the plane along the optical axis.

    None when the optical axis is parallel to the plane.
    """
    n_z = abs(float(plane_eq[2]))
    if n_z < 1e-6:
        return None
    return abs(float(plane_eq[3])) / n_z


def apply_distance_offset(plane_eq: np.ndarray, offset_mm: float) -> np.ndarray:
    """Moves the plane by offset_mm along the optical axis, keeping its normal.

    Positive moves it farther from the camera. Raises ValueError if the plane
    would end up behind the camera.
    """
    normal = plane_eq[:3] / float(np.linalg.norm(plane_eq[:3]))
    height_mm = abs(float(plane_eq[3])) / float(np.linalg.norm(plane_eq[:3]))
    corrected_height_mm = height_mm + offset_mm * abs(float(normal[2]))
    if not np.isfinite(corrected_height_mm) or corrected_height_mm <= 0:
        raise ValueError("Offset would move the support surface behind the camera")

    d = float(np.copysign(corrected_height_mm, plane_eq[3]))
    return np.array([*normal, d], dtype=np.float32)
