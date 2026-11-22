"""Six-pose IMU calibration math, following the Intel RealSense D435i procedure.

DepthAI applies the stored calibration as
    calibrated = Q @ (R @ raw) + b
where R is the IMU -> camera rotation stored in the IMU extrinsics and [Q|b] is the
accelerometer or gyroscope calibration. Inputs here are ACCELEROMETER_RAW and
GYROSCOPE_RAW samples, which are in the sensor-native frame.
"""

from dataclasses import dataclass
from itertools import permutations, product
from typing import List, Optional, Sequence

import numpy as np

GRAVITY = 9.80665  # m/s^2
POSE_ANGLE_TOLERANCE_DEG = 20.0
MAX_POSE_ERROR = 0.3  # m/s^2, worst per-pose residual after calibration
MAX_SCALE_CORRECTION = 0.1  # max |Q - I| element
MAX_ACCEL_BIAS = 2.0  # m/s^2
MAX_GYRO_BIAS = 0.1  # rad/s


@dataclass(frozen=True)
class Pose:
    instruction: str
    # Direction of the measured specific force (opposite of gravity) in the camera
    # RDF frame (x right, y down, z forward) while the device rests in this pose.
    up: tuple


POSES = (
    Pose(
        "Place the camera in its natural orientation (tripod mount down), looking forward.",
        (0, -1, 0),
    ),
    Pose("Rotate counter clockwise 90 degrees, still facing forward.", (-1, 0, 0)),
    Pose(
        "Rotate counter clockwise another 90 degrees until the camera is upside down.",
        (0, 1, 0),
    ),
    Pose("Rotate counter clockwise another 90 degrees.", (1, 0, 0)),
    Pose("Put the camera face down on the desk.", (0, 0, -1)),
    Pose("Put the camera face up on the desk.", (0, 0, 1)),
)


@dataclass(frozen=True)
class ImuCalibration:
    rotation: np.ndarray  # 3x3 IMU -> camera rotation (signed permutation)
    accelerometer: np.ndarray  # 3x4 [Q|b], applied after rotation
    gyroscope: np.ndarray  # 3x4 [I|b], applied after rotation
    pose_errors: np.ndarray  # per-pose |calibrated - expected| in m/s^2
    problems: List[str]  # reasons not to flash; empty when the result looks sane


def _find_problems(
    accelerometer: np.ndarray, gyroscope: np.ndarray, pose_errors: np.ndarray
) -> List[str]:
    problems = []
    if pose_errors.max() > MAX_POSE_ERROR:
        worst = int(pose_errors.argmax()) + 1
        problems.append(
            f"Poses are inconsistent (pose {worst} is off by {pose_errors.max():.2f} m/s^2). Redo the capture."
        )
    if np.abs(accelerometer[:, :3] - np.eye(3)).max() > MAX_SCALE_CORRECTION:
        problems.append(
            "Accelerometer scale/axis correction is larger than 10%. "
            "Were the poses rotated clockwise, or face up/face down swapped?"
        )
    if np.linalg.norm(accelerometer[:, 3]) > MAX_ACCEL_BIAS:
        problems.append(f"Accelerometer bias is larger than {MAX_ACCEL_BIAS} m/s^2.")
    if np.linalg.norm(gyroscope[:, 3]) > MAX_GYRO_BIAS:
        problems.append(
            f"Gyroscope bias is larger than {MAX_GYRO_BIAS} rad/s; was the device moving?"
        )
    return problems


def _angle_deg(a: np.ndarray, b: np.ndarray) -> float:
    cos = np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
    return float(np.degrees(np.arccos(np.clip(cos, -1.0, 1.0))))


def orientation_error(
    accel_mean: np.ndarray, captured_means: Sequence[np.ndarray]
) -> Optional[str]:
    """Check the next pose against the poses already captured.

    Angles between gravity directions do not depend on the IMU mounting, so this
    works before R is known.
    """
    up = np.asarray(POSES[len(captured_means)].up, dtype=float)
    for idx, captured in enumerate(captured_means):
        expected = _angle_deg(up, np.asarray(POSES[idx].up, dtype=float))
        measured = _angle_deg(accel_mean, captured)
        if abs(measured - expected) > POSE_ANGLE_TOLERANCE_DEG:
            return f"Wrong orientation: expected {expected:.0f} deg from pose {idx + 1}, measured {measured:.0f} deg."
    return None


def _nearest_rotation_permutation(m: np.ndarray) -> np.ndarray:
    """Closest proper signed permutation matrix (det = +1) in Frobenius norm."""
    candidates = []
    for perm, signs in product(permutations(range(3)), product((-1.0, 1.0), repeat=3)):
        r = np.diag(signs) @ np.eye(3)[list(perm)]
        if np.linalg.det(r) > 0:
            candidates.append(r)
    return max(candidates, key=lambda r: np.trace(r.T @ m))


def calibrate(accel_means: np.ndarray, gyro_means: np.ndarray) -> ImuCalibration:
    """Fit R and [Q|b] from per-pose mean raw accelerometer (Nx3) and gyroscope (Nx3) readings."""
    targets = np.asarray([pose.up for pose in POSES], dtype=float) * GRAVITY
    design = np.hstack([accel_means, np.ones((len(accel_means), 1))])
    solution = np.linalg.lstsq(design, targets, rcond=None)[0]
    q_total, accel_bias = solution[:3].T, solution[3]

    # q_total = Q @ R: R absorbs the axis mapping, Q keeps the small scale/misalignment part.
    rotation = _nearest_rotation_permutation(q_total)
    pose_errors = np.linalg.norm(accel_means @ q_total.T + accel_bias - targets, axis=1)
    # A static device has zero angular rate, so the bias cancels the mean rotated reading.
    gyro_bias = -rotation @ gyro_means.mean(axis=0)
    accelerometer = np.hstack([q_total @ rotation.T, accel_bias[:, None]])
    gyroscope = np.hstack([np.eye(3), gyro_bias[:, None]])
    return ImuCalibration(
        rotation=rotation,
        accelerometer=accelerometer,
        gyroscope=gyroscope,
        pose_errors=pose_errors,
        problems=_find_problems(accelerometer, gyroscope, pose_errors),
    )
