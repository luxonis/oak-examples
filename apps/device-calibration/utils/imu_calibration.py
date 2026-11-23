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

from dataclasses import dataclass, replace
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
MIN_BOARD_VIEWS = 6
# Alternating u / R steps converge linearly (~0.97 per step at 35 deg spread): 100 leaves 0.4 deg.
MAX_REFINE_ITERATIONS = 5000
MIN_VIEW_SPREAD_DEG = 30.0
MAX_BOARD_RESIDUAL_DEG = 0.5


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
    scale: np.ndarray  # (3,) per-axis accelerometer scale
    offset: np.ndarray  # (3,) per-axis accelerometer offset (raw units)
    gyro_mean: np.ndarray  # (3,) mean raw gyroscope reading while static


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
    gyro_mean = gyro_means.mean(axis=0)
    accelerometer, gyroscope = _matrices(rotation, scale, offset, gyro_mean)
    return ImuCalibration(
        rotation=rotation,
        accelerometer=accelerometer,
        gyroscope=gyroscope,
        pose_tilts=pose_tilts,
        fit_error=fit_error,
        problems=_find_problems(
            scale, accelerometer[:, 3], gyroscope[:, 3], pose_tilts, fit_error
        ),
        scale=scale,
        offset=offset,
        gyro_mean=gyro_mean,
    )


def _matrices(
    rotation: np.ndarray, scale: np.ndarray, offset: np.ndarray, gyro_mean: np.ndarray
) -> Tuple[np.ndarray, np.ndarray]:
    # R @ diag(scale) @ (raw - offset) == Q @ (R @ raw) + b
    accel_bias = -rotation @ (scale * offset)
    # A static device has zero angular rate, so the bias cancels the mean rotated reading.
    gyro_bias = -rotation @ gyro_mean
    return (
        np.hstack([rotation @ np.diag(scale) @ rotation.T, accel_bias[:, None]]),
        np.hstack([np.eye(3), gyro_bias[:, None]]),
    )


def with_rotation(result: ImuCalibration, rotation: np.ndarray) -> ImuCalibration:
    """Same fit with another IMU -> camera rotation: only [Q|b] depend on it."""
    accelerometer, gyroscope = _matrices(
        rotation, result.scale, result.offset, result.gyro_mean
    )
    return replace(
        result, rotation=rotation, accelerometer=accelerometer, gyroscope=gyroscope
    )


@dataclass(frozen=True)
class Mounting:
    rotation: np.ndarray  # 3x3 IMU -> to_cam rotation
    source: str  # 'board' | 'six-pose'
    reason: str  # why 'six-pose' was kept, or what the refinement used
    sets: int
    spread_deg: Optional[float]  # largest angle between any two views of gravity
    residual_deg: Optional[float]  # median angle between R a_i and B_i u_b


def refine_rotation(
    accel: np.ndarray, board_to_cam: np.ndarray, init: np.ndarray
) -> Mounting:
    """IMU -> camera rotation from a board that stayed still while the device moved.

    accel is (N,3) corrected accelerometer means, board_to_cam is (N,3,3). Gravity has one
    direction u in the board frame, so R a_i = B_i u for every view; solve R and u alternately.
    """
    n = len(accel)
    a = accel / np.linalg.norm(accel, axis=1, keepdims=True) if n else accel
    spread = (
        max(_angle_deg(x, y) for x in a for y in a) if n > 1 else None
    )

    def keep(reason: str, residual: Optional[float] = None) -> Mounting:
        return Mounting(init, "six-pose", reason, n, spread, residual)

    if n < MIN_BOARD_VIEWS:
        return keep(f"Only {n} still views with IMU data.")
    if spread < MIN_VIEW_SPREAD_DEG:
        return keep(
            f"The device was tilted only {spread:.0f} deg between views; {MIN_VIEW_SPREAD_DEG:.0f} deg are needed."
        )
    rotation = init
    for _ in range(MAX_REFINE_ITERATIONS):
        u = np.einsum("nji,nj->ni", board_to_cam, a @ rotation.T).mean(axis=0)
        u /= np.linalg.norm(u)
        u_cam = board_to_cam @ u  # (N,3)
        # Kabsch: the rotation taking each a_i onto B_i u, det forced to +1.
        left, _, right = np.linalg.svd(a.T @ u_cam)
        flip = np.diag([1, 1, np.sign(np.linalg.det(right.T @ left.T))])
        new = right.T @ flip @ left.T
        done = np.abs(new - rotation).max() < 1e-9
        rotation = new
        if done:
            break
    residual = float(
        np.median([_angle_deg(r, t) for r, t in zip(a @ rotation.T, u_cam)])
    )
    if residual >= MAX_BOARD_RESIDUAL_DEG:
        return keep(
            f"Residual {residual:.1f} deg: the board or device moved during captures.",
            residual,
        )
    return Mounting(
        rotation,
        "board",
        f"Refined from {n} board views, residual {residual:.2f} deg.",
        n,
        spread,
        residual,
    )


def spec_error(rotation: np.ndarray, spec_rotation: np.ndarray) -> Tuple[List[float], float]:
    """Roll/pitch/yaw (deg) of rotation @ spec^T, and its total angle (deg)."""
    d = rotation @ spec_rotation.T
    roll = np.arctan2(d[2, 1], d[2, 2])
    pitch = -np.arcsin(np.clip(d[2, 0], -1, 1))
    yaw = np.arctan2(d[1, 0], d[0, 0])
    total = np.arccos(np.clip((np.trace(d) - 1) / 2, -1, 1))
    return np.degrees([roll, pitch, yaw]).tolist(), float(np.degrees(total))


if __name__ == "__main__":
    # Self-check: python3 -m utils.imu_calibration
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

    # (e) with_rotation keeps |Q (R raw) + b| = g for any R.
    other = np.array([[0.0, 1, 0], [1, 0, 0], [0, 0, -1]])
    moved = with_rotation(result, other)
    for raw in means:
        assert abs(np.linalg.norm(moved.accelerometer[:, :3] @ (other @ raw) + moved.accelerometer[:, 3]) - GRAVITY) < 1e-6

    # Board refinement: gravity is fixed in the board frame, the device moves.
    def rot(axis: np.ndarray, degrees: float) -> np.ndarray:
        axis = axis / np.linalg.norm(axis)
        k = np.array([[0, -axis[2], axis[1]], [axis[2], 0, -axis[0]], [-axis[1], axis[0], 0]])
        a = np.radians(degrees)
        return np.eye(3) + np.sin(a) * k + (1 - np.cos(a)) * k @ k

    def views(n: int, max_degrees: float) -> np.ndarray:  # board -> camera, N x 3 x 3
        return np.array([rot(rng.normal(size=3), rng.uniform(0, max_degrees)) for _ in range(n)])

    spec = np.array([[0.0, 1, 0], [1, 0, 0], [0, 0, -1]])
    angles = (1.5, -2.0, 0.8)
    truth = rot(np.array([0.0, 0, 1]), angles[2]) @ rot(np.array([0.0, 1, 0]), angles[1]) @ rot(np.array([1.0, 0, 0]), angles[0]) @ spec
    gravity = np.array([0.1, -1.0, 0.3]) / np.linalg.norm([0.1, -1.0, 0.3])

    def imu_accel(board_to_cam: np.ndarray) -> np.ndarray:
        a = np.array([truth.T @ b @ gravity for b in board_to_cam]) * GRAVITY
        return np.array([tilted(v, 0.05) for v in a])

    motion = views(12, 60)  # 12 orientations, ~60+ deg apart at most
    fixed = refine_rotation(imu_accel(motion), motion, spec)
    err = np.degrees(np.arccos(np.clip((np.trace(fixed.rotation.T @ truth) - 1) / 2, -1, 1)))
    assert fixed.source == "board" and err < 0.1, (fixed, err)
    got, total = spec_error(fixed.rotation, spec)
    assert np.allclose(got, angles, atol=0.1), got

    moved_board = np.array([m @ rot(rng.normal(size=3), rng.uniform(20, 90)) for m in motion])
    wrong = refine_rotation(imu_accel(moved_board), motion, spec)
    assert wrong.source == "six-pose" and "Residual" in wrong.reason and wrong.rotation is spec, wrong
    few = refine_rotation(imu_accel(motion[:4]), motion[:4], spec)
    assert few.source == "six-pose" and "Only 4" in few.reason, few
    flat = views(12, 5)  # up to 10 deg between views
    narrow = refine_rotation(imu_accel(flat), flat, spec)
    assert narrow.source == "six-pose" and "tilted only" in narrow.reason, narrow
    print("calibration self-check passed")
