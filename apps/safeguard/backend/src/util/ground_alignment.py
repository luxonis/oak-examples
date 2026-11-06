import numpy as np


def rotation_from_imu(imu_g: np.ndarray) -> np.ndarray | None:
    """Map camera-frame points to a ground-aligned frame using IMU data.

    Built from an IMU accelerometer reading; in this pipeline imu_g points
    along world-up in camera coordinates, so we negate to get world-down.
    If IMU reports gravity-down directly, pass `-gravity` to this function.

    Args:
        imu_g: Accelerometer vector pointing toward world-up in camera axes.

    Returns:
        A 3x3 rotation matrix, or None for a degenerate orientation.
    """
    return rotation_from_down_vector(-np.asarray(imu_g, dtype=np.float32))


def rotation_from_down_vector(down_vector: np.ndarray) -> np.ndarray | None:
    """Build a camera-to-ground rotation from a world-down vector.

    Camera frame: x=right, y=down, z=forward.
    Ground-aligned frame: x'=right, y'=down, z'=forward-on-ground.

    Args:
        down_vector: Three-component world-down vector in camera axes.

    Returns:
        A 3x3 rotation matrix, or None if the direction is degenerate.

    Raises:
        ValueError: The input does not have exactly three components.
    """
    down_vector = np.asarray(down_vector, dtype=np.float32)
    if down_vector.shape != (3,):
        raise ValueError(f"Expected a 3D vector, got shape {down_vector.shape}")

    norm = float(np.linalg.norm(down_vector))
    if norm <= 1e-6:
        return None
    down = down_vector / norm

    cam_z = np.array([0.0, 0.0, 1.0], dtype=np.float32)
    forward = cam_z - np.dot(cam_z, down) * down
    forward_norm = float(np.linalg.norm(forward))
    if forward_norm <= 1e-6:
        return None
    forward /= forward_norm

    right = np.cross(down, forward)
    right_norm = float(np.linalg.norm(right))
    if right_norm <= 1e-6:
        return None
    right /= right_norm

    return np.stack([right, down, forward], axis=0)


def camera_to_ground(points: np.ndarray, R: np.ndarray) -> np.ndarray:
    """Rotate (N, 3) points from camera frame into the ground-aligned frame."""
    return points @ R.T


def ground_to_camera(points: np.ndarray, R: np.ndarray) -> np.ndarray:
    """Rotate (N, 3) points from the ground-aligned frame back to camera frame."""
    return points @ R
