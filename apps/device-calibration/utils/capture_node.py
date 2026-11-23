"""Live board detection, guidance, previews and set capture (CaptureNode), plus DatasetReplay for no-device runs."""

import json
import math
import sys
import threading
import time
from dataclasses import asdict
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import cv2
import depthai as dai
import numpy as np

from utils.charuco import BoardSpec, Detection, _key, _read_gray, detect, make_board, object_points
from utils.guidance import (
    BUCKETS, GRID, CaptureStats, camera_cells, can_process, coverage, is_novel, is_ready,
    next_step, pair_cells, pair_stats, pose_bucket, pose_counts,
)

PREVIEW_WIDTH = 640
LIVE_WIDTH = 960
MOTION_PX = 1.5  # mean corner displacement between groups that still counts as still
STILL_GROUPS = 3
MIN_INTERVAL = 1.0  # s between auto captures
FULL_TIMEOUT = 4.0  # s to wait for a full-resolution group per attempt (18 MB takes ~2 s over 100 Mbit)
FAILED = "Capture failed: cameras did not deliver a synchronized full-resolution set."
Shot = Tuple[List[str], Dict[str, np.ndarray], Optional[str]]  # cameras, cell masks, pose bucket
_GROUP = [dai.Node.DatatypeHierarchy(dai.DatatypeEnum.MessageGroup, True)]
_FRAME = [dai.Node.DatatypeHierarchy(dai.DatatypeEnum.ImgFrame, True)]


def _gray(img: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img


def _nv12(bgr: np.ndarray) -> dai.ImgFrame:
    frame = dai.ImgFrame()
    frame.setCvFrame(bgr[: bgr.shape[0] // 2 * 2, : bgr.shape[1] // 2 * 2], dai.ImgFrame.Type.NV12)
    frame.setTimestamp(dai.Clock.now())
    return frame


def _live_size(img: np.ndarray) -> np.ndarray:
    if img.shape[1] <= LIVE_WIDTH:
        return img
    return cv2.resize(img, (LIVE_WIDTH, round(img.shape[0] * LIVE_WIDTH / img.shape[1])))


def _pairs(cfg: dict, enabled: List[str]) -> List[Tuple[str, str]]:
    edges = [(s, c["extrinsics"]["to_cam"]) for s, c in cfg["cameras"].items() if s in enabled and "extrinsics" in c]
    if cfg.get("stereo_config"):
        edges.append((cfg["stereo_config"]["left_cam"], cfg["stereo_config"]["right_cam"]))
    seen, pairs = set(), []
    for a, b in edges:
        if a in enabled and b in enabled and frozenset((a, b)) not in seen:
            seen.add(frozenset((a, b)))
            pairs.append((a, b))
    return pairs


def _cells(corners: np.ndarray, size: Tuple[int, int]) -> np.ndarray:
    mask = np.zeros((GRID, GRID), bool)
    cols = np.clip(corners[:, 0] / size[0] * GRID, 0, GRID - 1).astype(int)
    rows = np.clip(corners[:, 1] / size[1] * GRID, 0, GRID - 1).astype(int)
    mask[rows, cols] = True
    return mask


def _tilt(det: Detection, board, hfov: float) -> Optional[Tuple[float, float]]:
    """(yaw, pitch) in degrees of the board normal, from solvePnP with K from hfov and no distortion."""
    w, h = det.size
    f = (w / 2) / math.tan(math.radians(hfov) / 2)
    ok, rvec, _ = cv2.solvePnP(object_points(board, det.ids), det.corners, np.array([[f, 0, w / 2], [0, f, h / 2], [0, 0, 1]]), None)
    if not ok:
        return None
    n = cv2.Rodrigues(rvec)[0][:, 2]
    n = -n if n[2] > 0 else n  # normal toward the camera
    return math.degrees(math.atan2(n[0], -n[2])), math.degrees(math.atan2(n[1], -n[2]))


class CaptureNode(dai.node.ThreadedHostNode):
    """Detects the board in the live groups, guides the user and saves full-resolution sets.

    Services call `state()`/`action()` from another thread; detection and capture run in `run()`.
    """

    def __init__(self) -> None:
        super().__init__()
        self.live_input = self.createInput(blocking=False, queueSize=1)
        self.full_input = self.createInput(blocking=False, queueSize=4)
        self.previews: Dict[str, dai.Node.Output] = {}
        self._lock = threading.Lock()
        self._active = False
        self._stats: Optional[CaptureStats] = None

    def build(
        self,
        live_out: dai.Node.Output,
        full_out: dai.Node.Output,
        sockets: List[str],
        request_full: Callable[[List[str]], None],
    ) -> "CaptureNode":
        live_out.link(self.live_input)
        full_out.link(self.full_input)
        self._sockets = sockets
        self._request_full = request_full
        self.previews = {s: self.createOutput(name=s, possibleDatatypes=_FRAME) for s in sockets}
        return self

    def start(
        self,
        board_cfg: dict,
        spec: BoardSpec,
        board_fixed: bool,
        dataset_dir: Path,
        accel_mean: Callable[[], Optional[List[float]]],
    ) -> None:
        cameras = board_cfg["cameras"]
        enabled = [s for s in self._sockets if cameras.get(s, {}).get("enabled", True)]
        board = make_board(spec)
        with self._lock:
            self._stats = CaptureStats({s: cameras[s]["name"] for s in enabled}, _pairs(board_cfg, enabled), board_fixed)
            self._hfov = {s: cameras[s]["hfov"] for s in enabled}
            self._board, self._detector = board, cv2.aruco.CharucoDetector(board)
            self._spec, self._dir, self._accel_mean = spec, Path(dataset_dir), accel_mean
            self._records: List[dict] = []
            self._previous: Dict[str, Tuple[np.ndarray, np.ndarray]] = {}
            self._still, self._last_set = 0, 0.0
            self._auto, self._manual, self._saving, self._view = True, False, False, None
            self._message = ""
            self._dir.mkdir(parents=True, exist_ok=True)
            self._write_sets()
            self._active = True

    def stop(self) -> None:
        with self._lock:
            self._active = False

    def run(self) -> None:
        while self.isRunning():
            group = self.live_input.get()
            frames = {n: group[n].getCvFrame() for n in group.getMessageNames()}
            previews, shot = self._on_live(frames)
            for socket, img in previews.items():
                self.previews[socket].send(_nv12(img))
            if shot:
                self._capture(shot)

    def _on_live(self, frames: Dict[str, np.ndarray]) -> Tuple[Dict[str, np.ndarray], Optional[Shot]]:
        """One live group: detect, update stats, draw. Needs no device, so the dataset self-check uses it too."""
        with self._lock:
            if not self._active:
                return {}, None
            stats = self._stats
        views: Dict[str, Tuple[Detection, np.ndarray]] = {}
        tilts: Dict[str, Tuple[float, float]] = {}
        for s in stats.names:
            if s not in frames:
                continue
            det = detect(_gray(frames[s]), self._detector, refine=False)
            if det is not None:
                views[s] = (det, _cells(det.corners, det.size))
                tilt = _tilt(det, self._board, self._hfov[s])
                if tilt:
                    tilts[s] = tilt
        motion = max((self._motion(s, d) for s, (d, _) in views.items()), default=math.inf)
        with self._lock:
            self._previous = {s: (d.ids, d.corners) for s, (d, _) in views.items()}
            self._still = self._still + 1 if motion < MOTION_PX else 0
            stats.live = {s: m for s, (_, m) in views.items()}
            stats.area = {s: cv2.contourArea(cv2.convexHull(d.corners)) / (d.size[0] * d.size[1]) for s, (d, _) in views.items()}
            stats.live_bucket = next((pose_bucket(*tilts[s]) for s in stats.names if s in tilts), None)
            stats.moving = bool(views) and self._still < STILL_GROUPS
            need, manual, self._manual = min(2, len(stats.names)), self._manual, False
            shot = None
            if self._active and not self._saving and len(views) >= need and self._still >= STILL_GROUPS and (
                manual or (self._auto and time.monotonic() - self._last_set >= MIN_INTERVAL and is_novel(stats))
            ):
                shot = (list(views), dict(stats.live), stats.live_bucket)
            guidance = next_step(stats)
            drawn = {s: self._draw(s, frames[s], views.get(s), guidance) for s in stats.names if s in frames}
        return drawn, shot

    def _motion(self, socket: str, det: Detection) -> float:
        ids, corners = self._previous.get(socket, (np.empty(0, np.int32), None))
        _, now, before = np.intersect1d(det.ids, ids, return_indices=True)
        if not len(now):
            return math.inf
        return float(np.linalg.norm(det.corners[now] - corners[before], axis=1).mean())

    def _view_mask(self, socket: str) -> np.ndarray:
        stats = self._stats
        if self._view:
            a, b = self._view.split("-")
            if socket in (a, b):
                return pair_cells(stats, a, b, socket)
        return camera_cells(stats, socket)

    def _draw(self, socket: str, frame: np.ndarray, view: Optional[Tuple[Detection, np.ndarray]], guidance) -> np.ndarray:
        h, w = frame.shape[:2]
        scale = PREVIEW_WIDTH / w
        img = cv2.resize(frame if frame.ndim == 3 else cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR), (PREVIEW_WIDTH, round(h * scale)))
        ch, cw = img.shape[0] / GRID, img.shape[1] / GRID
        cell = lambda r, c: ((int(c * cw), int(r * ch)), (int((c + 1) * cw), int((r + 1) * ch)))
        layer = img.copy()
        for r, c in np.argwhere(self._view_mask(socket)):
            cv2.rectangle(layer, *cell(r, c), (0, 200, 0), -1)
        img = cv2.addWeighted(layer, 0.35, img, 0.65, 0)
        if guidance.camera == socket:
            for r, c in guidance.target_cells:
                cv2.rectangle(img, *cell(r, c), (0, 255, 255), 2)
        if view is None:
            cv2.rectangle(img, (0, 0), (img.shape[1] - 1, img.shape[0] - 1), (0, 0, 255), 6)
        else:
            for x, y in view[0].corners * scale:
                cv2.circle(img, (int(x), int(y)), 3, (255, 0, 255), -1)
        label = self._stats.names[socket] + (f"  shared {self._view}" if self._view and socket in self._view.split("-") else "")
        cv2.putText(img, label, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        return img

    def _poll_full(self) -> Optional[Dict[str, np.ndarray]]:
        group = self.full_input.tryGet()
        return None if group is None else {n: _gray(group[n].getCvFrame()) for n in group.getMessageNames()}

    def _grab_full(self, cameras: List[str]) -> Optional[Dict[str, np.ndarray]]:
        """First complete full-resolution group after a request; one retry; extras are dropped."""
        for _ in range(2):
            while self._poll_full() is not None:  # leftovers of an earlier capture
                pass
            self._request_full(cameras)
            deadline = time.monotonic() + FULL_TIMEOUT
            while time.monotonic() < deadline:
                full = self._poll_full()
                if full is None:
                    time.sleep(0.01)
                elif all(c in full for c in cameras):
                    return full
        return None

    def _capture(self, shot: Shot) -> None:
        cameras, masks, bucket = shot
        with self._lock:
            self._saving, self._message = True, ""
        full = self._grab_full(cameras)
        accel = self._accel_mean()
        saved = [c for c in cameras if full and c in full]
        key = f"{len(self._records) + 1:04d}"  # undo is refused while saving, so the count cannot change
        for c in saved:
            path = self._dir / self._stats.names[c] / f"{key}.png"
            path.parent.mkdir(exist_ok=True)
            cv2.imwrite(str(path), full[c])
        with self._lock:
            self._saving = False
            if full is None:
                self._message = FAILED
                return
            self._stats.add({c: masks[c] for c in saved}, bucket)
            self._records.append({"key": key, "cameras": saved, "accel": accel})
            self._last_set = time.monotonic()
            self._write_sets()

    def _write_sets(self) -> None:
        (self._dir / "sets.json").write_text(
            json.dumps({"spec": asdict(self._spec), "boardFixed": self._stats.board_fixed, "sets": self._records})
        )

    def state(self) -> dict:
        with self._lock:
            stats = self._stats
            if stats is None:
                return {}
            guidance = next_step(stats)
            return {
                "sets": len(stats.sets),
                "auto": self._auto,
                "ready": is_ready(stats),
                "canProcess": can_process(stats) and not self._saving,
                "saving": self._saving,
                "grid": GRID,
                "guidance": {"text": guidance.text, "camera": guidance.camera},
                "cameras": {
                    s: {
                        "coverage": coverage(camera_cells(stats, s)),
                        "detected": s in stats.live,
                        "sets": sum(s in x for x in stats.sets),
                    }
                    for s in stats.names
                },
                "pairs": [
                    {"key": p.key, "a": p.a, "b": p.b, "shared": p.shared, "need": p.need,
                     "coverageA": p.coverage_a, "coverageB": p.coverage_b, "ok": p.ok}
                    for p in pair_stats(stats)
                ],
                "view": self._view,
                "poses": {b: {"have": n, "need": BUCKETS[b]} for b, n in pose_counts(stats).items()},
                "message": self._message,
            }

    def action(self, name: str, value=None) -> bool:
        with self._lock:
            if not self._active:
                return False
            if name == "capture":
                self._manual = bool(self._stats.live) and not self._saving
                return self._manual
            if name == "undo_set":
                if self._saving or not self._stats.sets:
                    return False
                self._stats.undo()
                record = self._records.pop()
                for c in record["cameras"]:
                    (self._dir / self._stats.names[c] / f"{record['key']}.png").unlink(missing_ok=True)
                self._write_sets()
                return True
            if name == "set_auto":
                self._auto = bool(value)
                return True
            if name == "set_view":
                if value is not None and value not in {p.key for p in pair_stats(self._stats)}:
                    return False
                self._view = value
                return True
            return False


class DatasetReplay(dai.node.ThreadedHostNode):
    """Plays a recorded dataset in place of the gates: each set as live groups (<= 960 px) for a while, looping."""

    def __init__(self) -> None:
        super().__init__()
        self.live_out = self.createOutput(name="live", possibleDatatypes=_GROUP)
        self.full_out = self.createOutput(name="full", possibleDatatypes=_GROUP)
        self._lock = threading.Lock()
        self._current: Dict[str, np.ndarray] = {}

    def build(self, dataset: Path, names: Dict[str, str], fps: float = 4, set_seconds: float = 2.0) -> "DatasetReplay":
        """names maps socket -> camera name (the folder `dataset/<name>/`); a set key is the file stem without `<name>_`."""
        found: Dict[str, Dict[str, Path]] = {}
        for socket, name in names.items():
            for f in sorted((Path(dataset) / name).glob("*.png")):
                found.setdefault(_key(f, name), {})[socket] = f
        self._sets = [found[k] for k in sorted(found)]
        self._fps, self._seconds = fps, set_seconds
        return self

    def request_full(self, sockets: List[str]) -> None:
        with self._lock:
            images = {s: self._current[s] for s in sockets if s in self._current}
        self.full_out.send(self._group(images))

    @staticmethod
    def _group(images: Dict[str, np.ndarray]) -> dai.MessageGroup:
        group = dai.MessageGroup()
        for socket, img in images.items():
            group[socket] = _nv12(cv2.cvtColor(img, cv2.COLOR_GRAY2BGR))
        return group

    def run(self) -> None:
        while self.isRunning():
            for files in self._sets:
                images = {s: _read_gray(f) for s, f in files.items()}
                with self._lock:
                    self._current = {s: i for s, i in images.items() if i is not None}
                live = {s: _live_size(i) for s, i in self._current.items()}
                end = time.monotonic() + self._seconds
                while self.isRunning() and time.monotonic() < end:
                    self.live_out.send(self._group(live))
                    time.sleep(1 / self._fps)


def _selfcheck(dataset: Path, out: Path) -> None:
    import shutil

    from utils.charuco import load_dataset

    info = dict(l.split(": ") for l in (dataset / "target_info.txt").read_text().splitlines() if ": " in l)
    spec = BoardSpec(int(info["Number of squaresX"]), int(info["Number of squaresY"]),
                     float(info["Square Size"].split()[0]), float(info["Marker Size"].split()[0]))
    # left -> right -> tof -> rgb, like target_info.txt; tof images withheld from three sets
    cam = {"CAM_B": "left", "CAM_C": "right", "CAM_D": "tof", "CAM_A": "rgb"}
    cfg = {"cameras": {s: {"name": n, "hfov": 70.0, "enabled": True,
                           **({"extrinsics": {"to_cam": t}} if t else {})}
                       for (s, n), t in zip(cam.items(), ["CAM_C", "CAM_D", "CAM_A", None])},
           "stereo_config": {"left_cam": "CAM_B", "right_cam": "CAM_C"}}
    src = out / "dataset_ALL_copy"
    shutil.rmtree(src, ignore_errors=True)
    for n in cam.values():
        (src / n).mkdir(parents=True)
        for f in (dataset / n).glob("*.png"):
            (src / n / f.name).symlink_to(f)
    withheld = sorted((src / "tof").glob("*.png"))[:3]
    for f in withheld:
        f.unlink()
    result = out / "dataset_captured"
    shutil.rmtree(result, ignore_errors=True)

    with dai.Pipeline(False) as p:
        replay = p.create(DatasetReplay).build(src, cam, fps=10, set_seconds=4.0)
        node = p.create(CaptureNode).build(replay.live_out, replay.full_out, list(cam), replay.request_full)
        node.start(cfg, spec, False, result, lambda: [0.0, 0.0, 9.81])
        p.start()
        time.sleep(4.0 * len(replay._sets) + 3)  # one pass over the sets plus margin
        auto = node.state()
        node.action("set_auto", False)
        while node.state()["saving"]:  # a capture already under way finishes first
            time.sleep(0.1)
        time.sleep(1)
        snap = lambda s: {
            "sets": s["sets"], "poses": s["poses"], "pairs": s["pairs"],
            "cameras": {k: (c["coverage"], c["sets"]) for k, c in s["cameras"].items()},  # not the live "detected" flag
        }
        before = snap(node.state())
        for _ in range(100):
            node.action("capture")
            time.sleep(0.2)
            if node.state()["sets"] > before["sets"]:
                break
        added = snap(node.state())
        print("  sets before / after manual capture:", before["sets"], added["sets"])
        assert added != before and node.action("undo_set")
        after = snap(node.state())
        assert after == before, [(k, before[k], after[k]) for k in before if before[k] != after[k]]
        print(f"auto-captured {auto['sets']} sets in one pass over {len(replay._sets)} (manual + undo restored exactly)")

        names = {s: n for s, n in cam.items()}
        for s, c in node.state()["cameras"].items():
            print(f"  camera {names[s]:6s} coverage {c['coverage']:.0%} in {c['sets']} sets")
        for pr in node.state()["pairs"]:
            print(f"  pair {names[pr['a']]}-{names[pr['b']]}: {pr['shared']}/{pr['need']} shared, "
                  f"coverage {pr['coverageA']:.0%} / {pr['coverageB']:.0%}, ok={pr['ok']}")
        print("  poses", node.state()["poses"], "| guidance:", node.state()["guidance"]["text"])
        assert auto["sets"] >= 15 and all(p["shared"] for p in auto["pairs"])

        # previews: camera view vs pair view of the same frames
        node.action("set_auto", False)
        frames = {s: _live_size(_read_gray(f)) for s, f in replay._sets[5].items()}
        cam_view, _ = node._on_live(frames)
        key = node.state()["pairs"][1]["key"]
        assert node.action("set_view", key) and not node.action("set_view", "nope")
        pair_view, _ = node._on_live(frames)
        node.action("set_view", None)
        for s in cam:
            cv2.imwrite(str(out / f"preview_{cam[s]}_camera.png"), cam_view[s])
            cv2.imwrite(str(out / f"preview_{cam[s]}_pair_{key}.png"), pair_view[s])
        differ = [cam[s] for s in cam if not np.array_equal(cam_view[s], pair_view[s])]
        print("previews written to", out, "; differ between camera and pair view:", differ)
        assert differ

        # a request_full that never answers: "Capture failed" after one retry, nothing saved
        n, asked = node.state()["sets"], []
        node._request_full = lambda c: asked.append(c)
        node._capture((list(cam), {s: np.ones((GRID, GRID), bool) for s in cam}, None))
        print("silent request_full:", len(asked), "requests ->", node.state()["message"])
        assert len(asked) == 2 and node.state()["message"] == FAILED and node.state()["sets"] == n
        p.stop()

    sets = json.loads((result / "sets.json").read_text())
    print("sets.json:", len(sets["sets"]), "sets; cameras per set:", sorted({len(s["cameras"]) for s in sets["sets"]}),
          "; first:", sets["sets"][0])
    assert len(sets["sets"]) == n and any("CAM_D" not in s["cameras"] for s in sets["sets"])
    obs = load_dataset(result, cam, spec)
    for s, d in obs.items():
        print(f"  load_dataset {cam[s]}: {len(d)}/{len(list((result / cam[s]).glob('*.png')))} detected at full size")
    for s, name in cam.items():
        assert len(list((result / name).glob("*.png"))) == sum(s in r["cameras"] for r in sets["sets"])
    print("capture_node checks ok")


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[3] / ".design" / "wp4"
    root.mkdir(parents=True, exist_ok=True)
    _selfcheck(Path(sys.argv[1]), root)
