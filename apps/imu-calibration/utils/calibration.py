"""Six-pose IMU calibration math.

DepthAI applies the stored calibration as
    calibrated = Q @ (R @ raw) + b
where R is the IMU -> camera rotation stored in the IMU extrinsics and [Q|b] is the
accelerometer or gyroscope calibration. Inputs here are ACCELEROMETER_RAW and
GYROSCOPE_RAW samples, which are in the sensor-native frame.

The accelerometer fit only assumes that gravity has the same magnitude in every pose,
not that each pose is exactly axis-aligned, so a device held a few degrees off does not
bias the result.
"""

from dataclasses import dataclass
from itertools import permutations, product
from typing import List, Optional, Sequence, Tuple

import numpy as np

GRAVITY = 9.80665  # m/s^2
POSE_ANGLE_TOLERANCE_DEG = 20.0
MAX_FIT_ERROR = 0.05  # m/s^2; above this the magnitude fit did not converge
MAX_SCALE_CORRECTION = 0.1  # max |scale - 1| per axis
MAX_ACCEL_BIAS = 2.0  # m/s^2
MAX_GYRO_BIAS = 0.1  # rad/s
FIT_ITERATIONS = 30


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
    pose_tilts: (
        np.ndarray
    )  # per-pose angle (deg) between measured gravity and the guide
    fit_error: float  # worst per-pose | |calibrated| - g | in m/s^2
    problems: List[str]  # reasons not to flash; empty when the result looks sane


def _find_problems(
    scale: np.ndarray,
    accel_bias: np.ndarray,
    gyro_bias: np.ndarray,
    pose_tilts: np.ndarray,
    fit_error: float,
) -> List[str]:
    problems = []
    worst = int(pose_tilts.argmax())
    if pose_tilts[worst] > POSE_ANGLE_TOLERANCE_DEG:
        problems.append(
            f"Pose {worst + 1} is {pose_tilts[worst]:.0f} deg away from the guide. "
            "Were the poses rotated clockwise, or face up/face down swapped?"
        )
    if not fit_error <= MAX_FIT_ERROR:  # also catches NaN from a diverged fit
        problems.append("The accelerometer fit did not converge. Redo the capture.")
    if np.abs(scale - 1).max() > MAX_SCALE_CORRECTION:
        problems.append("Accelerometer scale correction is larger than 10%.")
    if np.linalg.norm(accel_bias) > MAX_ACCEL_BIAS:
        problems.append(f"Accelerometer bias is larger than {MAX_ACCEL_BIAS} m/s^2.")
    if np.linalg.norm(gyro_bias) > MAX_GYRO_BIAS:
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
    """Proper signed permutation matrix (det = +1) that maximizes trace(R^T m)."""
    candidates = []
    for perm, signs in product(permutations(range(3)), product((-1.0, 1.0), repeat=3)):
        r = np.diag(signs) @ np.eye(3)[list(perm)]
        if np.linalg.det(r) > 0:
            candidates.append(r)
    return max(candidates, key=lambda r: np.trace(r.T @ m))


def _fit_scale_offset(means: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Per-axis scale and offset so that |scale * (raw - offset)| = g in every pose.

    Gauss-Newton, started from the classic up/down estimate of each axis.
    """
    high, low = means.max(axis=0), means.min(axis=0)
    offset = (high + low) / 2
    scale = 2 * GRAVITY / (high - low)
    for _ in range(FIT_ITERATIONS):
        centered = means - offset
        norms = np.linalg.norm(centered * scale, axis=1)
        jacobian = (
            np.hstack([scale * centered**2, -(scale**2) * centered]) / norms[:, None]
        )
        step = np.linalg.lstsq(jacobian, GRAVITY - norms, rcond=None)[0]
        scale, offset = scale + step[:3], offset + step[3:]
    return scale, offset


def calibrate(accel_means: np.ndarray, gyro_means: np.ndarray) -> ImuCalibration:
    """Fit R and [Q|b] from per-pose mean raw accelerometer (Nx3) and gyroscope (Nx3) readings."""
    scale, offset = _fit_scale_offset(accel_means)
    corrected = (accel_means - offset) * scale  # IMU frame, |corrected| = g
    up = np.asarray([pose.up for pose in POSES], dtype=float)
    # R maps the corrected gravity directions onto the guide directions.
    rotation = _nearest_rotation_permutation(up.T @ corrected)
    pose_tilts = np.array(
        [_angle_deg(c, u) for c, u in zip(corrected @ rotation.T, up)]
    )
    fit_error = float(np.abs(np.linalg.norm(corrected, axis=1) - GRAVITY).max())
    # R @ diag(scale) @ (raw - offset) == Q @ (R @ raw) + b
    accel_bias = -rotation @ (scale * offset)
    # A static device has zero angular rate, so the bias cancels the mean rotated reading.
    gyro_bias = -rotation @ gyro_means.mean(axis=0)
    return ImuCalibration(
        rotation=rotation,
        accelerometer=np.hstack(
            [rotation @ np.diag(scale) @ rotation.T, accel_bias[:, None]]
        ),
        gyroscope=np.hstack([np.eye(3), gyro_bias[:, None]]),
        pose_tilts=pose_tilts,
        fit_error=fit_error,
        problems=_find_problems(scale, accel_bias, gyro_bias, pose_tilts, fit_error),
    )


if __name__ == "__main__":
    # Self-check: python3 -m utils.calibration
    rng = np.random.default_rng(0)
    up = np.asarray([pose.up for pose in POSES], dtype=float) * GRAVITY
    rotation = np.array([[1.0, 0, 0], [0, -1, 0], [0, 0, -1]])
    scale, offset = 1 + rng.normal(0, 0.03, 3), rng.normal(0, 0.4, 3)

    def raw_of(gravity_in_camera: np.ndarray) -> np.ndarray:
        return rotation.T @ gravity_in_camera / scale + offset

    def tilted(v: np.ndarray, degrees: float) -> np.ndarray:
        axis = np.cross(v, rng.normal(size=3))
        axis /= np.linalg.norm(axis)
        a = np.radians(degrees)
        return (
            v * np.cos(a)
            + np.cross(axis, v) * np.sin(a)
            + axis * axis.dot(v) * (1 - np.cos(a))
        )

    means = np.array([raw_of(tilted(u, 5)) for u in up])  # 5 deg hand tilt per pose
    result = calibrate(means, np.zeros((len(POSES), 3)))
    assert (
        np.allclose(result.rotation, rotation) and not result.problems
    ), result.problems
    q, b = result.accelerometer[:, :3], result.accelerometer[:, 3]
    for _ in range(
        100
    ):  # firmware applies Q @ (R @ raw) + b; any orientation must read g
        raw = raw_of(tilted(up[0], rng.uniform(0, 180)))
        assert abs(np.linalg.norm(q @ (result.rotation @ raw) + b) - GRAVITY) < 1e-6
    mirrored = means[[0, 3, 2, 1, 4, 5]]  # poses rotated clockwise instead
    assert calibrate(mirrored, np.zeros((len(POSES), 3))).problems
    print("calibration self-check passed")
