"""Calibration quality checks. Old and new calibrations go through the same code. No depthai."""

from dataclasses import asdict
from itertools import combinations
from typing import List, Optional, Tuple

import cv2
import numpy as np

from .camera_calibration import CameraCalib, Rig, common, normalize, project, transform
from .charuco import BoardSpec, Detection, Observations, make_board, object_points

MAX_EPIPOLAR_PX = 0.8
GRID = 12


def _max_rms(height: int) -> float:
    return max(1.0, height / 720)


def board_pose(calib: CameraCalib, det: Detection, board) -> np.ndarray:
    """4x4 board -> camera, cm. Solved on normalized points, so any lens model works."""
    ok, rvec, tvec = cv2.solvePnP(
        object_points(board, det.ids), normalize(calib, det.corners), np.eye(3), None
    )
    pose = np.eye(4)
    pose[:3, :3], pose[:3, 3] = cv2.Rodrigues(rvec)[0], tvec.reshape(3)
    return pose


def camera_rms(calib: CameraCalib, dets: List[Detection], board) -> float:
    sq = []
    for det in dets:
        pose = board_pose(calib, det, board)
        X = object_points(board, det.ids) @ pose[:3, :3].T + pose[:3, 3]
        sq.append(np.sum((project(calib, X) - det.corners) ** 2, axis=1))
    return float(np.sqrt(np.mean(np.concatenate(sq))))


def cross_reprojection(
    rig: Rig, a: str, b: str, obs: Observations, board
) -> Optional[Tuple[float, int]]:
    """Board pose seen by a, moved into b through the rig, projected into b: (rms px in b, views)."""
    T = transform(rig, a, b)
    if T is None or a not in rig.cameras or b not in rig.cameras:
        return None
    sq = []
    for key in obs.get(a, {}).keys() & obs.get(b, {}).keys():
        ids, ca, cb = common(obs[a][key], obs[b][key])
        if len(ids) < 6:
            continue
        pose = T @ board_pose(rig.cameras[a], Detection(ca, ids, obs[a][key].size), board)
        X = object_points(board, ids) @ pose[:3, :3].T + pose[:3, 3]
        sq.append(np.sum((project(rig.cameras[b], X) - cb) ** 2, axis=1))
    if not sq:
        return None
    return float(np.sqrt(np.mean(np.concatenate(sq)))), len(sq)


def epipolar_error(rig: Rig, left: str, right: str, obs: Observations, board) -> Optional[float]:
    """Mean row (column for a vertical baseline) offset of matching corners after rectification, px."""
    T = transform(rig, left, right)
    if rig.rectification is None or T is None or left not in rig.cameras or right not in rig.cameras:
        return None
    axis = 1 if abs(T[0, 3]) >= abs(T[1, 3]) else 0
    cl, cr = rig.cameras[left], rig.cameras[right]
    diffs = []
    for key in obs.get(left, {}).keys() & obs.get(right, {}).keys():
        _, pl, pr = common(obs[left][key], obs[right][key])
        # R rotates into the rectified frame, whose normalized coordinates share rows
        nl = normalize(cl, pl, rig.rectification[0])
        nr = normalize(cr, pr, rig.rectification[1])
        diffs.append(np.abs(nl[:, axis] - nr[:, axis]))
    if not diffs:
        return None
    return float(np.mean(np.concatenate(diffs)) * np.mean([cl.K[0, 0], cr.K[0, 0]]))


def _coverage(dets: List[Detection]) -> float:
    cells = set()
    for d in dets:
        w, h = d.size
        cells |= set(zip((d.corners[:, 0] * GRID / w).astype(int).tolist(),
                         (d.corners[:, 1] * GRID / h).astype(int).tolist()))
    return len(cells) / GRID**2


def report(new: Rig, old: Optional[Rig], board_cfg: dict, obs: Observations, spec: BoardSpec) -> dict:
    board = make_board(spec)
    problems: List[str] = []
    warnings: List[str] = []
    name = {s: c["name"] for s, c in board_cfg["cameras"].items()}

    def worse(label: str, n: Optional[float], o: Optional[float]) -> None:
        if n is not None and o is not None and n > o:
            warnings.append(f"{label}: new {n:.2f} px is worse than old {o:.2f} px.")

    cameras = []
    for socket, calib in new.cameras.items():
        dets = list(obs[socket].values())
        rms_new = camera_rms(calib, dets, board)
        rms_old = camera_rms(old.cameras[socket], dets, board) if old and socket in old.cameras else None
        limit = _max_rms(calib.size[1])
        if rms_new > limit:
            problems.append(f"{name[socket]}: reprojection error {rms_new:.2f} px is above {limit:.2f} px.")
        worse(f"{name[socket]} reprojection", rms_new, rms_old)
        cameras.append({"socket": socket, "name": name[socket], "model": calib.model,
                        "size": list(calib.size), "views": len(dets), "coverage": _coverage(dets),
                        "rmsNew": rms_new, "rmsOld": rms_old})

    pairs = []
    for a, b in combinations(sorted(new.cameras), 2):
        res = cross_reprojection(new, a, b, obs, board)
        if res is None:
            continue
        o = old and cross_reprojection(old, a, b, obs, board)
        limit = 2 * max(_max_rms(new.cameras[a].size[1]), _max_rms(new.cameras[b].size[1]))
        if res[0] > limit:
            problems.append(f"{name[a]} -> {name[b]}: cross-camera error {res[0]:.2f} px is above {limit:.2f} px.")
        worse(f"{name[a]} -> {name[b]}", res[0], o and o[0])
        pairs.append({"from": a, "to": b, "views": res[1], "newPx": res[0], "oldPx": o[0] if o else None})

    stereo = None
    cfg = board_cfg.get("stereo_config")
    ep_new = cfg and epipolar_error(new, cfg["left_cam"], cfg["right_cam"], obs, board)
    if ep_new is not None:
        ep_old = old and epipolar_error(old, cfg["left_cam"], cfg["right_cam"], obs, board)
        if ep_new > MAX_EPIPOLAR_PX:
            problems.append(f"Stereo epipolar error {ep_new:.2f} px is above {MAX_EPIPOLAR_PX} px.")
        worse("Stereo epipolar", ep_new, ep_old)
        stereo = {"left": cfg["left_cam"], "right": cfg["right_cam"],
                  "epipolarNew": ep_new, "epipolarOld": ep_old}

    return {
        "cameras": cameras, "pairs": pairs, "stereo": stereo,
        "problems": problems, "warnings": warnings,
        "charuco": asdict(spec),
        "rig": {
            "cameras": {s: {"K": c.K.tolist(), "dist": c.dist.tolist(), "model": c.model,
                            "size": list(c.size)} for s, c in new.cameras.items()},
            "extrinsics": {f"{a}-{b}": T.tolist() for (a, b), T in new.extrinsics.items()},
        },
    }
