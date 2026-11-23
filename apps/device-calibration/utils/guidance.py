"""Capture bookkeeping and guidance. Pure numpy, no depthai or OpenCV.

Everything is derived from `CaptureStats.sets`, so undoing a set is a pop and cannot leave counters stale.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

GRID = 12
CELLS = GRID * GRID
CAMERA_COVERAGE = 0.7
PAIR_COVERAGE = 0.5
PAIR_SETS = 12  # shared sets a pair needs to be ready
MIN_SETS = 5  # hard minimum for calibrating a camera or pair
NEW_CELLS = 3  # cells a set must add to count as novel
BUCKETS = {"frontal": 4, "left": 2, "right": 2, "up": 2, "down": 2}  # pose bucket -> sets needed
CLOSE_AREA = 0.25  # board area fraction below which "move closer" beats "move to the edge"

Mask = np.ndarray  # (GRID, GRID) bool
_WHERE = {
    (0, 0): "top-left", (0, 1): "top", (0, 2): "top-right",
    (1, 0): "left", (1, 1): "center", (1, 2): "right",
    (2, 0): "bottom-left", (2, 1): "bottom", (2, 2): "bottom-right",
}
_TILT = {
    "left": "Tilt the board about 30 deg to the left.",
    "right": "Tilt the board about 30 deg to the right.",
    "up": "Tilt the board about 30 deg up.",
    "down": "Tilt the board about 30 deg down.",
    "frontal": "Face the board straight at the camera.",
}
_TILT_FIXED = {
    "left": "Tilt the device so the board looks turned about 30 deg to the left.",
    "right": "Tilt the device so the board looks turned about 30 deg to the right.",
    "up": "Tilt the device so the board looks turned about 30 deg up.",
    "down": "Tilt the device so the board looks turned about 30 deg down.",
    "frontal": "Face the device straight at the board.",
}


@dataclass
class CaptureStats:
    names: Dict[str, str]  # enabled socket -> camera name
    pairs: List[Tuple[str, str]]
    board_fixed: bool = False
    sets: List[Dict[str, Mask]] = field(default_factory=list)  # a camera is in a set only if it saw the board
    buckets: List[Optional[str]] = field(default_factory=list)  # pose bucket of each set
    live: Dict[str, Mask] = field(default_factory=dict)  # latest group: cells hit per camera that sees the board
    area: Dict[str, float] = field(default_factory=dict)  # latest group: board area fraction per camera
    live_bucket: Optional[str] = None
    moving: bool = False

    def add(self, masks: Dict[str, Mask], bucket: Optional[str]) -> None:
        self.sets.append(masks)
        self.buckets.append(bucket)

    def undo(self) -> None:
        self.sets.pop()
        self.buckets.pop()


@dataclass
class PairStat:
    key: str
    a: str
    b: str
    shared: int
    need: int
    coverage_a: float
    coverage_b: float
    ok: bool


@dataclass
class Guidance:
    text: str
    camera: Optional[str] = None
    target_cells: List[Tuple[int, int]] = field(default_factory=list)  # (row, col)


def pose_bucket(yaw: float, pitch: float) -> Optional[str]:
    """Bucket of a board tilt in degrees (yaw > 0: normal toward image right, pitch > 0: toward image bottom)."""
    if max(abs(yaw), abs(pitch)) < 12:
        return "frontal"
    if max(abs(yaw), abs(pitch)) < 20:
        return None
    if abs(yaw) >= abs(pitch):
        return "right" if yaw > 0 else "left"
    return "down" if pitch > 0 else "up"


def cells_of(masks: List[Mask]) -> Mask:
    return np.any(masks, axis=0) if masks else np.zeros((GRID, GRID), bool)


def camera_cells(stats: CaptureStats, socket: str) -> Mask:
    return cells_of([s[socket] for s in stats.sets if socket in s])


def shared_sets(stats: CaptureStats, a: str, b: str) -> List[Dict[str, Mask]]:
    return [s for s in stats.sets if a in s and b in s]


def pair_cells(stats: CaptureStats, a: str, b: str, of: str) -> Mask:
    """Cells of camera `of` (a or b) covered by the sets both cameras saw."""
    return cells_of([s[of] for s in shared_sets(stats, a, b)])


def coverage(mask: Mask) -> float:
    return float(mask.sum()) / CELLS


def pose_counts(stats: CaptureStats) -> Dict[str, int]:
    return {b: stats.buckets.count(b) for b in BUCKETS}


def pair_stats(stats: CaptureStats) -> List[PairStat]:
    out = []
    for a, b in stats.pairs:
        shared = len(shared_sets(stats, a, b))
        ca, cb = (coverage(pair_cells(stats, a, b, s)) for s in (a, b))
        out.append(PairStat(f"{a}-{b}", a, b, shared, PAIR_SETS, ca, cb,
                            shared >= PAIR_SETS and ca >= PAIR_COVERAGE and cb >= PAIR_COVERAGE))
    return out


def _unmet(stats: CaptureStats) -> List[str]:
    have = pose_counts(stats)
    return [b for b, need in BUCKETS.items() if have[b] < need]


def is_ready(stats: CaptureStats) -> bool:
    """A good total cannot hide a pair that is behind."""
    return (
        all(coverage(camera_cells(stats, s)) >= CAMERA_COVERAGE for s in stats.names)
        and all(p.ok for p in pair_stats(stats))
        and not _unmet(stats)
    )


def can_process(stats: CaptureStats) -> bool:
    return all(sum(s in x for x in stats.sets) >= MIN_SETS for s in stats.names) and all(
        p.shared >= MIN_SETS for p in pair_stats(stats)
    )


def is_novel(stats: CaptureStats) -> bool:
    """Would the latest live group add >= NEW_CELLS cells to a camera or to a pair, or fill an unmet pose bucket."""
    if stats.live_bucket in _unmet(stats):
        return True
    if any((m & ~camera_cells(stats, s)).sum() >= NEW_CELLS for s, m in stats.live.items()):
        return True
    return any(
        (stats.live[s] & ~pair_cells(stats, a, b, s)).sum() >= NEW_CELLS
        for a, b in stats.pairs
        if a in stats.live and b in stats.live
        for s in (a, b)
    )


def _region(uncovered: Mask) -> Tuple[str, List[Tuple[int, int]]]:
    """Where the uncovered cells are (centroid third of the grid) and those cells inside that third."""
    rows, cols = np.nonzero(uncovered)
    third = GRID // 3
    ri, ci = (min(int(rows.mean()) // third, 2), min(int(cols.mean()) // third, 2))
    cells = [(int(r), int(c)) for r, c in zip(rows, cols) if r // third == ri and c // third == ci]
    return _WHERE[ri, ci], cells or np.argwhere(uncovered).tolist()


def next_step(stats: CaptureStats) -> Guidance:
    names, fixed = stats.names, stats.board_fixed
    if not stats.live:
        return Guidance("Show the whole board to the cameras.")
    if stats.moving:
        return Guidance("Hold still.")
    pairs = pair_stats(stats)
    behind = sorted((p for p in pairs if p.shared < p.need), key=lambda p: p.shared)
    if behind:
        p = behind[0]
        both = f"{names[p.a]} and {names[p.b]}"
        text = (f"Position the device so both {both} see the board" if fixed
                else f"Hold the board where both {both} see it")
        return Guidance(f"{text} ({p.shared} of {p.need} shared views).")
    weak = sorted((p for p in pairs if not p.ok), key=lambda p: min(p.coverage_a, p.coverage_b))
    if weak:
        p = weak[0]
        c, partner = (p.a, p.b) if p.coverage_a <= p.coverage_b else (p.b, p.a)
        where, cells = _region(~pair_cells(stats, p.a, p.b, c))
        move = f"Move the device so the board is at the {where} of" if fixed else f"Move the board to the {where} of"
        return Guidance(f"{move} {names[c]}, keeping it visible in {names[partner]}.", c, cells)
    low = sorted((s for s in names if coverage(camera_cells(stats, s)) < CAMERA_COVERAGE),
                 key=lambda s: coverage(camera_cells(stats, s)))
    if low:
        s = low[0]
        uncovered = ~camera_cells(stats, s)
        if not uncovered[1:-1, 1:-1].any() and stats.area.get(s, 1.0) < CLOSE_AREA:
            text = "Move the device closer" if fixed else "Move closer"
            return Guidance(f"{text} so the board reaches the edges of {names[s]}.", s, np.argwhere(uncovered).tolist())
        where, cells = _region(uncovered)
        move = f"Move the device so the board is at the {where} of" if fixed else f"Move the board to the {where} of"
        return Guidance(f"{move} {names[s]}.", s, cells)
    unmet = _unmet(stats)
    if unmet:
        return Guidance((_TILT_FIXED if fixed else _TILT)[unmet[0]])
    return Guidance("Coverage complete. Press Process.")


if __name__ == "__main__":
    def mask(cells: int) -> Mask:
        m = np.zeros(CELLS, bool)
        m[:cells] = True
        return m.reshape(GRID, GRID)

    full = mask(CELLS)
    names = {"A": "left", "B": "right", "C": "rgb"}
    ok_poses = ["frontal"] * 4 + ["left", "left", "right", "right", "up", "up", "down", "down"]

    def stats(sets, pairs=(("A", "B"), ("B", "C")), live=("A", "B", "C"), moving=False, fixed=False, **kw):
        used = {c for p in pairs for c in p} | set(live)
        s = CaptureStats({c: names[c] for c in sorted(used)}, list(pairs), fixed, moving=moving, area=kw.get("area", {}))
        s.live = {c: full for c in live}
        for masks, bucket in sets:
            s.add(masks, bucket)
        return s

    ab = lambda m, n: [({"A": m, "B": m}, None)] * n
    unbalanced = stats(ab(mask(92), 30) + [({"B": mask(92), "C": mask(1)}, None)])  # 64 % coverage
    left_half = mask(60)  # top 5 rows: 42 % < 50 %
    cases = [
        ("1 no camera", stats([], live=()), "Show the whole board"),
        ("2 moving", stats([], moving=True), "Hold still."),
        ("3 unbalanced", unbalanced, "both right and rgb see it (1 of 12"),
        ("4 pair coverage", stats(ab(left_half, 12), pairs=(("A", "B"),), live=("A", "B")),
         "Move the board to the bottom of left, keeping it visible in right."),
        ("4 fixed wording", stats(ab(left_half, 12), pairs=(("A", "B"),), live=("A", "B"), fixed=True),
         "Move the device so the board is at the bottom of left"),
        ("5 camera coverage", stats(ab(mask(90), 12), pairs=(("A", "B"),), live=("A", "B")),
         "Move the board to the bottom"),
        ("5 move closer", stats([({"A": np.pad(np.ones((10, 10), bool), 1)}, None)] * 12, pairs=(), live=("A",),
                                area={"A": 0.1}), "Move closer so the board reaches the edges of left."),
        ("6 bucket", stats([({"A": full}, b) for b in ["frontal"] * 4 + ["right"] * 2 + ["up"] * 2 + ["down"] * 2],
                           pairs=(), live=("A",)), "Tilt the board about 30 deg to the left."),
        ("7 ready", stats([({"A": full, "B": full}, b) for b in ok_poses], pairs=(("A", "B"),), live=("A", "B")),
         "Coverage complete"),
    ]
    for label, st, expect in cases:
        g = next_step(st)
        print(f"{label}: {g.text} (camera {g.camera}, {len(g.target_cells)} target cells)")
        assert expect in g.text, (label, g.text)
    assert not is_ready(unbalanced) and "rgb" in next_step(unbalanced).text
    p = pair_stats(unbalanced)
    assert (p[0].shared, round(p[0].coverage_a, 2), p[1].shared, p[1].coverage_b) == (30, 0.64, 1, 1 / CELLS)
    assert coverage(camera_cells(unbalanced, "C")) == 1 / CELLS
    assert is_ready(cases[-1][1]) and can_process(cases[-1][1]) and not can_process(unbalanced)
    # a set that adds only pair cells is novel; once nothing is new it is not
    s = stats([({"A": mask(60), "B": mask(60)}, "frontal")] * 3,
              pairs=(("A", "B"),), live=("A", "B"))
    s.sets += [{"A": full}] * 2  # camera A is fully covered, but its pair cells stop at 60
    s.buckets += ["left", "right"]
    s.live, s.live_bucket = {"A": full, "B": mask(60)}, "frontal"
    assert (s.live["A"] & ~camera_cells(s, "A")).sum() == 0 and is_novel(s)
    s.live, s.live_bucket = {"A": mask(60), "B": mask(60)}, None
    assert not is_novel(s)
    n = pair_stats(s)[0].shared
    s.add({"A": full, "B": full}, "up")
    s.undo()
    assert pair_stats(s)[0].shared == n and len(s.buckets) == len(s.sets)
    assert pose_bucket(0, 0) == "frontal" and pose_bucket(-30, 5) == "left" and pose_bucket(5, -30) == "up" and pose_bucket(15, 0) is None
    print("guidance checks ok")
