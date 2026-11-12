"""Gravity acceptance shared by candidate search and supplied-plane verification."""

import numpy as np


def is_valid_horizontal_plane(
    plane_eq: np.ndarray, gravity: np.ndarray, max_gravity_angle_deg: float
) -> bool:
    """Accept a normalized plane opposing raw gravity with nonpositive offset."""
    normalized_gravity = gravity / (np.linalg.norm(gravity) + 1e-9)
    return bool(
        np.dot(plane_eq[:3], normalized_gravity)
        <= -np.cos(np.deg2rad(max_gravity_angle_deg))
        and plane_eq[3] <= 0
    )


def gravity_angle_deg(plane_eq: np.ndarray, gravity: np.ndarray) -> float:
    """Angle between a normalized plane normal and the direction opposing gravity."""
    normalized_gravity = gravity / (np.linalg.norm(gravity) + 1e-9)
    cosine = float(np.clip(-np.dot(plane_eq[:3], normalized_gravity), -1.0, 1.0))
    return float(np.degrees(np.arccos(cosine)))
