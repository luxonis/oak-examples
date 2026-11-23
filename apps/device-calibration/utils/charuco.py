"""ChArUco board: spec, detection, rendering and dataset loading. Pure OpenCV, no depthai."""

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import cv2
import numpy as np

DICTIONARIES: List[str] = sorted(n for n in dir(cv2.aruco) if n.startswith("DICT_"))
MIN_CORNERS = 6
_SUBPIX = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10000, 1e-5)


@dataclass(frozen=True)
class BoardSpec:
    squares_x: int
    squares_y: int
    square_cm: float
    marker_cm: float
    dictionary: str = "DICT_4X4_1000"

    def problem(self) -> Optional[str]:
        if self.squares_x < 3 or self.squares_y < 3:
            return "The board needs at least 3 x 3 squares."
        if not 0 < self.marker_cm < self.square_cm:
            return "The marker size must be larger than 0 and smaller than the square size."
        if self.dictionary not in DICTIONARIES:
            return f"Unknown dictionary {self.dictionary}."
        have = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, self.dictionary)).bytesList.shape[0]
        need = self.squares_x * self.squares_y // 2
        if need > have:
            return f"The board needs {need} markers, {self.dictionary} has {have}."
        return None


@dataclass
class Detection:
    corners: np.ndarray  # (N,2) float32 px
    ids: np.ndarray  # (N,) int32
    size: Tuple[int, int]  # (w, h)


Observations = Dict[str, Dict[str, Detection]]  # socket -> set key -> Detection


def make_board(spec: BoardSpec) -> cv2.aruco.CharucoBoard:
    dictionary = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, spec.dictionary))
    return cv2.aruco.CharucoBoard(
        (spec.squares_x, spec.squares_y), spec.square_cm, spec.marker_cm, dictionary
    )


def detect(
    gray: np.ndarray, detector: cv2.aruco.CharucoDetector, refine: bool = True
) -> Optional[Detection]:
    corners, ids, _, _ = detector.detectBoard(gray)
    if ids is None or len(ids) < MIN_CORNERS:
        return None
    corners = corners.reshape(-1, 2).astype(np.float32)
    if refine:
        cv2.cornerSubPix(gray, corners.reshape(-1, 1, 2), (5, 5), (-1, -1), _SUBPIX)
    return Detection(corners, ids.reshape(-1).astype(np.int32), (gray.shape[1], gray.shape[0]))


def object_points(board: cv2.aruco.CharucoBoard, ids: np.ndarray) -> np.ndarray:
    return np.asarray(board.getChessboardCorners())[ids].reshape(-1, 3)


def render_png(spec: BoardSpec, width_px: int = 600) -> bytes:
    height = round(width_px * spec.squares_y / spec.squares_x)
    ok, png = cv2.imencode(".png", make_board(spec).generateImage((width_px, height), marginSize=10))
    return png.tobytes()


def _key(path: Path, name: str) -> str:
    return path.stem.removeprefix(name + "_")


def _read_gray(path: Path) -> Optional[np.ndarray]:
    img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE | cv2.IMREAD_ANYDEPTH)
    if img is not None and img.dtype != np.uint8:  # 16-bit ToF amplitude
        img = cv2.normalize(img, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
    return img


def load_dataset(
    path: str | Path,
    names: Dict[str, str],
    spec: BoardSpec,
    progress: Callable[[float, str], None] = lambda f, s: None,
) -> Observations:
    """names maps socket -> camera name (the folder `path/<name>/`). Failed detections are skipped."""
    detector = cv2.aruco.CharucoDetector(make_board(spec))
    files = {s: sorted((Path(path) / n).glob("*.png")) for s, n in names.items()}
    total, done = max(sum(map(len, files.values())), 1), 0
    obs: Observations = {}
    for socket, name in names.items():
        obs[socket] = {}
        for f in files[socket]:
            progress(done / total, f"Detecting {name} {len(obs[socket]) + 1}/{len(files[socket])}")
            done += 1
            gray = _read_gray(f)
            det = None if gray is None else detect(gray, detector)
            if det is not None:
                obs[socket][_key(f, name)] = det
    return obs


if __name__ == "__main__":
    lab = BoardSpec(12, 9, 6.0, 4.7)
    for spec, other in (
        (lab, BoardSpec(12, 9, 6.0, 4.7, "DICT_5X5_250")),
        (BoardSpec(7, 5, 6.0, 4.7, "DICT_5X5_250"), BoardSpec(7, 5, 6.0, 4.7)),
    ):
        img = cv2.imdecode(np.frombuffer(render_png(spec, 1200), np.uint8), cv2.IMREAD_GRAYSCALE)
        own = detect(img, cv2.aruco.CharucoDetector(make_board(spec)))
        wrong = detect(img, cv2.aruco.CharucoDetector(make_board(other)))
        n = (spec.squares_x - 1) * (spec.squares_y - 1)
        print(f"{spec.squares_x}x{spec.squares_y} {spec.dictionary}: own {own and len(own.ids)}/{n}, "
              f"other dictionary {wrong and len(wrong.ids)}")
        assert own is not None and len(own.ids) == n and wrong is None
    for bad in (BoardSpec(12, 9, 4.0, 4.0), BoardSpec(12, 9, 6.0, 4.7, "DICT_X"),
                BoardSpec(30, 30, 6.0, 4.7, "DICT_4X4_50"), BoardSpec(2, 9, 6.0, 4.7)):
        assert bad.problem(), bad
    assert lab.problem() is None
    assert _key(Path("left_10_0.0_-30.0_930.png"), "left") == _key(Path("10_0.0_-30.0_930.png"), "left")
    assert _key(Path("p0_0.png"), "left") == "p0_0"
    print("render/problem/key checks ok")

    if len(sys.argv) > 1:
        root = Path(sys.argv[1])
        nx, ny, sq, mk = (int(a) if i < 2 else float(a) for i, a in enumerate(sys.argv[2:6])) \
            if len(sys.argv) >= 6 else (29, 20, 5.0, 3.75)
        names = {d.name: d.name for d in sorted(root.iterdir()) if d.is_dir() and any(d.glob("*.png"))}
        obs = load_dataset(root, names, BoardSpec(nx, ny, sq, mk))
        for cam, sets in obs.items():
            total = len(list((root / cam).glob("*.png")))
            print(f"{cam}: {len(sets)}/{total} detected, corners min {min(len(d.ids) for d in sets.values())}")
        keys = [set(s) for s in obs.values()]
        print("shared set keys across cameras:", len(set.intersection(*keys)))
