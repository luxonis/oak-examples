"""Camera intrinsics and extrinsics from ChArUco detections. Pure OpenCV/numpy, no depthai."""

from collections import deque
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

import cv2
import numpy as np

from .charuco import BoardSpec, Detection, Observations, make_board, object_points

MIN_PAIR_SETS = 5


class CalibrationError(Exception):
    pass


@dataclass
class CameraCalib:
    K: np.ndarray
    dist: np.ndarray
    model: str  # 'perspective' | 'fisheye'
    size: Tuple[int, int]
    rms: Optional[float] = None


@dataclass
class Rig:
    cameras: Dict[str, CameraCalib]
    extrinsics: Dict[Tuple[str, str], np.ndarray]  # (src, dst) -> 4x4, cm, p_dst = T @ p_src
    rectification: Optional[Tuple[np.ndarray, np.ndarray]] = None  # (R_left, R_right)


def normalize(calib: CameraCalib, pts: np.ndarray, R: Optional[np.ndarray] = None) -> np.ndarray:
    """Pixels (N,2) -> undistorted normalized coordinates (N,2), optionally rotated by R."""
    pts = pts.reshape(-1, 1, 2).astype(np.float64)
    if calib.model == "fisheye":
        return cv2.fisheye.undistortPoints(pts, calib.K, calib.dist, R=R).reshape(-1, 2)
    # the default 5 iterations are too few for strong rational distortion
    term = (cv2.TERM_CRITERIA_COUNT + cv2.TERM_CRITERIA_EPS, 100, 1e-12)
    return cv2.undistortPointsIter(pts, calib.K, calib.dist, R, None, term).reshape(-1, 2)


def project(calib: CameraCalib, X: np.ndarray) -> np.ndarray:
    """Camera-frame points (N,3) -> pixels (N,2)."""
    X = X.reshape(-1, 1, 3).astype(np.float64)
    proj = cv2.fisheye.projectPoints if calib.model == "fisheye" else cv2.projectPoints
    return proj(X, np.zeros(3), np.zeros(3), calib.K, calib.dist)[0].reshape(-1, 2)


def calibrate_intrinsics(dets: List[Detection], board, hfov: float, model: str) -> CameraCalib:
    if len(dets) < 3:
        raise CalibrationError(f"Only {len(dets)} usable views, 3 are needed.")
    w, h = dets[0].size
    fisheye = model == "fisheye"
    dtype = np.float64 if fisheye else np.float32  # the two OpenCV APIs want different types
    objs = [object_points(board, d.ids).reshape(-1, 1, 3).astype(dtype) for d in dets]
    imgs = [d.corners.reshape(-1, 1, 2).astype(dtype) for d in dets]
    f = (w / 2) / np.radians(hfov / 2) if fisheye else w / (2 * np.tan(np.radians(hfov) / 2))
    K = np.array([[f, 0, w / 2], [0, f, h / 2], [0, 0, 1.0]])
    term = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 1000, 1e-9)
    try:
        if fisheye:
            flags = (cv2.fisheye.CALIB_CHECK_COND | cv2.fisheye.CALIB_USE_INTRINSIC_GUESS
                     | cv2.fisheye.CALIB_RECOMPUTE_EXTRINSIC)
            rms, K, dist, _, _ = cv2.fisheye.calibrate(objs, imgs, (w, h), K, np.zeros((4, 1)),
                                                       flags=flags, criteria=term)
        else:
            flags = cv2.CALIB_USE_INTRINSIC_GUESS | cv2.CALIB_RATIONAL_MODEL
            rms, K, dist, _, _ = cv2.calibrateCamera(objs, imgs, (w, h), K, np.zeros(8),
                                                     flags=flags, criteria=term)
    except cv2.error as e:
        raise CalibrationError(f"{model} calibration failed: {e.msg.strip()}") from e
    return CameraCalib(K, dist.reshape(-1), model, (w, h), float(rms))


def _invert(T: np.ndarray) -> np.ndarray:
    inv = np.eye(4)
    inv[:3, :3] = T[:3, :3].T
    inv[:3, 3] = -T[:3, :3].T @ T[:3, 3]
    return inv


def common(a: Detection, b: Detection) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Shared corner ids and the matching pixels in a and b."""
    ids, ia, ib = np.intersect1d(a.ids, b.ids, return_indices=True)
    return ids, a.corners[ia], b.corners[ib]


def calibrate_pair(
    src: CameraCalib,
    dst: CameraCalib,
    pairs: List[Tuple[Detection, Detection]],
    board,
) -> Tuple[np.ndarray, float]:
    """Transform src -> dst and its RMS in pixels. Corners are undistorted per camera first, so
    different resolutions and models need no special case. OpenCV initializes the pose from the
    per-view board poses: a spec guess would break on cameras mounted rotated (dataset_ color)."""
    objs, pa, pb = [], [], []
    for a, b in pairs:
        ids, ca, cb = common(a, b)
        if len(ids) >= 6:
            objs.append(object_points(board, ids).reshape(-1, 1, 3))
            pa.append(normalize(src, ca).reshape(-1, 1, 2).astype(np.float32))
            pb.append(normalize(dst, cb).reshape(-1, 1, 2).astype(np.float32))
    if len(objs) < MIN_PAIR_SETS:
        raise CalibrationError("Not enough shared views")
    eye = np.eye(3)
    rms, _, _, _, _, R, T, *_ = cv2.stereoCalibrateExtended(
        objs, pa, pb, eye, np.zeros(5), eye, np.zeros(5), (1, 1),
        np.eye(3), np.zeros(3),
        flags=cv2.CALIB_FIX_INTRINSIC,
        criteria=(cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 300, 1e-12),
    )
    out = np.eye(4)
    out[:3, :3], out[:3, 3] = R, T.reshape(3)
    return out, float(rms * np.mean([src.K[0, 0], src.K[1, 1], dst.K[0, 0], dst.K[1, 1]]))


def transform(rig: Rig, src: str, dst: str) -> Optional[np.ndarray]:
    """Breadth-first search over the extrinsics edges and their inverses."""
    seen, queue = {src: np.eye(4)}, deque([src])
    while queue:
        cur = queue.popleft()
        for (a, b), T in rig.extrinsics.items():
            if cur == a:
                nxt, step = b, T
            elif cur == b:
                nxt, step = a, _invert(T)
            else:
                continue
            if nxt not in seen:
                seen[nxt] = step @ seen[cur]
                queue.append(nxt)
    return seen.get(dst)


def calibrate_rig(
    board_cfg: dict,
    obs: Observations,
    spec: BoardSpec,
    progress: Callable[[float, str], None] = lambda f, s: None,
) -> Rig:
    board = make_board(spec)
    cams = {
        s: c for s, c in board_cfg["cameras"].items() if c.get("enabled", True) and s in obs
    }
    rig = Rig({}, {})
    for i, (socket, cam) in enumerate(cams.items()):
        progress(i / (2 * len(cams)), f"Intrinsics {cam['name']}")
        if not obs[socket]:
            raise CalibrationError(f"The board was not detected by {cam['name']}.")
        rig.cameras[socket] = calibrate_intrinsics(
            list(obs[socket].values()), board, cam["hfov"], cam.get("model", "perspective")
        )
    edges = [
        (s, c["extrinsics"]["to_cam"])
        for s, c in cams.items()
        if c.get("extrinsics", {}).get("to_cam") in cams
    ]
    for i, (a, b) in enumerate(edges):
        progress(0.5 + i / (2 * len(edges)), f"Extrinsics {cams[a]['name']} -> {cams[b]['name']}")
        shared = [(obs[a][k], obs[b][k]) for k in obs[a].keys() & obs[b].keys()]
        try:
            rig.extrinsics[(a, b)], _ = calibrate_pair(rig.cameras[a], rig.cameras[b], shared, board)
        except CalibrationError as e:
            raise CalibrationError(f"{e} between {cams[a]['name']} and {cams[b]['name']}") from e
    stereo = board_cfg.get("stereo_config")
    T = stereo and transform(rig, stereo["left_cam"], stereo["right_cam"])
    if T is not None:
        left, right = rig.cameras[stereo["left_cam"]], rig.cameras[stereo["right_cam"]]
        if left.model == "fisheye":
            R1, R2 = cv2.fisheye.stereoRectify(
                left.K, left.dist, right.K, right.dist, left.size, T[:3, :3], T[:3, 3],
                cv2.fisheye.CALIB_ZERO_DISPARITY)[:2]
        else:
            R1, R2 = cv2.stereoRectify(
                left.K, left.dist, right.K, right.dist, left.size, T[:3, :3], T[:3, 3])[:2]
        rig.rectification = (R1, R2)
    progress(1.0, "Done")
    return rig


if __name__ == "__main__":
    from .validation import board_pose, cross_reprojection

    rng = np.random.default_rng(1)
    spec = BoardSpec(12, 9, 6.0, 4.7)
    board = make_board(spec)
    corners3d = np.asarray(board.getChessboardCorners())
    ids_all = np.arange(len(corners3d), dtype=np.int32)
    size = (1280, 800)

    def cam(model: str) -> CameraCalib:
        K = np.array([[900.0, 0, 645], [0, 905, 395], [0, 0, 1]])
        return CameraCalib(K, np.array([-0.2, 0.05, 0, 0, 0, 0, 0, 0]) if model == "perspective"
                           else np.array([0.05, -0.01, 0.0, 0.0]), model, size)

    def euler(d):
        return cv2.Rodrigues(np.radians(np.array(d, float)))[0]

    def pose4(R, t):
        T = np.eye(4)
        T[:3, :3], T[:3, 3] = R, t
        return T

    truth = Rig(
        {"CAM_A": cam("perspective"), "CAM_B": cam("fisheye"), "CAM_C": cam("perspective")},
        {("CAM_A", "CAM_B"): pose4(euler([0.3, -0.5, 0.2]), [-7.5, 0.1, 0.2]),
         ("CAM_B", "CAM_C"): pose4(euler([-0.2, 0.4, 0.6]), [3.8, -0.1, 0.1])},
    )
    # SYNTH: board in front of CAM_A; every set is visible to A and B, only sets 0-24 to C, A is missing in 5-9
    sets = []
    for i in range(30):
        board_to_a = pose4(cv2.Rodrigues(rng.normal(0, 0.5, 3))[0], [-33 + rng.normal(0, 3), -24 + rng.normal(0, 3), 120 + rng.normal(0, 10)])
        sets.append(board_to_a)

    def view(calib: CameraCalib, board_to_cam: np.ndarray) -> Optional[Detection]:
        X = (board_to_cam[:3, :3] @ corners3d.T).T + board_to_cam[:3, 3]
        px = project(calib, X)
        ok = (px[:, 0] > 0) & (px[:, 0] < size[0]) & (px[:, 1] > 0) & (px[:, 1] < size[1])
        if ok.sum() < 6:
            return None
        return Detection((px[ok] + rng.normal(0, 0.2, (ok.sum(), 2))).astype(np.float32), ids_all[ok], size)

    def synth(n_c: int, skip_a=range(5, 10)) -> Observations:
        out: Observations = {"CAM_A": {}, "CAM_B": {}, "CAM_C": {}}
        for i, ba in enumerate(sets):
            ba_b = truth.extrinsics[("CAM_A", "CAM_B")] @ ba
            ba_c = truth.extrinsics[("CAM_B", "CAM_C")] @ ba_b
            for sock, T, ok in (("CAM_A", ba, i not in skip_a), ("CAM_B", ba_b, True), ("CAM_C", ba_c, i < n_c)):
                d = ok and view(truth.cameras[sock], T)
                if d:
                    out[sock][f"s{i}"] = d
        return out

    def cfg(model_b="fisheye"):
        ext = lambda to, t: {"to_cam": to, "specTranslation": {"x": t[0], "y": t[1], "z": t[2]},
                             "rotation": {"r": 0, "p": 0, "y": 0}}
        return {"cameras": {
            "CAM_A": {"name": "a", "hfov": 70.0, "extrinsics": ext("CAM_B", [-7.5, 0, 0])},
            "CAM_B": {"name": "b", "hfov": 70.0, "model": model_b, "extrinsics": ext("CAM_C", [3.75, 0, 0])},
            "CAM_C": {"name": "c", "hfov": 70.0}},
            "stereo_config": {"left_cam": "CAM_A", "right_cam": "CAM_C"}}

    obs = synth(25)
    print({s: len(v) for s, v in obs.items()})
    rig = calibrate_rig(cfg(), obs, spec)
    for edge, T in rig.extrinsics.items():
        err = _invert(truth.extrinsics[edge]) @ T
        mm, deg = np.linalg.norm(err[:3, 3]) * 10, np.degrees(np.linalg.norm(cv2.Rodrigues(err[:3, :3])[0]))
        print(f"{edge}: {mm:.2f} mm, {deg:.3f} deg")
        assert mm < 1 and deg < 0.1
    print({s: round(c.rms, 3) for s, c in rig.cameras.items()})
    base = cross_reprojection(rig, "CAM_A", "CAM_C", obs, board)

    sparse = synth(3)  # camera C shares only 3 sets with B
    try:
        calibrate_rig(cfg(), sparse, spec)
        raise AssertionError("expected CalibrationError")
    except CalibrationError as e:
        print("CalibrationError:", e)

    bent = Rig(rig.cameras, dict(rig.extrinsics))
    bent.extrinsics[("CAM_B", "CAM_C")] = bent.extrinsics[("CAM_B", "CAM_C")] @ pose4(euler([1, 0, 0]), [0, 0, 0])
    worse = cross_reprojection(bent, "CAM_A", "CAM_C", obs, board)
    print(f"A->C cross error {base[0]:.3f} px ({base[1]} views) -> {worse[0]:.3f} px with 1 deg perturbation")
    assert worse[0] > 5 * base[0]

    T_true = sets[0]
    pose = board_pose(truth.cameras["CAM_A"], view(truth.cameras["CAM_A"], T_true), board)
    print("board_pose error mm:", round(float(np.linalg.norm(pose[:3, 3] - T_true[:3, 3]) * 10), 3))
    assert np.linalg.norm(pose[:3, 3] - T_true[:3, 3]) < 0.1

    import depthai as dai

    from .eeprom import apply_rig, rig_from_handler

    handler = dai.CalibrationHandler()
    apply_rig(handler, rig, cfg())
    back = rig_from_handler(handler, cfg(), {s: size for s in rig.cameras})
    for s, c in rig.cameras.items():
        assert np.allclose(back.cameras[s].K, c.K) and back.cameras[s].model == c.model, s
        assert np.allclose(back.cameras[s].dist[: len(c.dist)], c.dist), s
    for edge, T in rig.extrinsics.items():
        assert np.allclose(back.extrinsics[edge], T, atol=1e-5), edge
    assert np.allclose(back.rectification[0], rig.rectification[0], atol=1e-6)
    print("apply_rig / rig_from_handler round trip ok")
