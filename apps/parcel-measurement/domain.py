from dataclasses import dataclass, field
from enum import Enum
import math


class CalibrationPhase(str, Enum):
    IDLE = "idle"
    CALIBRATING = "calibrating"
    CHOOSING = "choosing"
    READY = "ready"
    FAILED = "failed"


@dataclass
class CalibrationSession:
    phase: CalibrationPhase = CalibrationPhase.IDLE
    generation: int = 0
    candidates: tuple = ()
    plane: object | None = None
    selected: int | None = None
    message: str = "Calibrate the empty support surface before measuring parcels."

    def start(self):
        if self.phase is CalibrationPhase.CALIBRATING:
            raise ValueError("Calibration is already running.")
        self.generation += 1
        self.phase = CalibrationPhase.CALIBRATING
        self.candidates = ()
        self.plane = None
        self.selected = None
        self.message = "Finding horizontal support planes. Keep the camera still."

    def finish(self, candidates):
        if self.phase is not CalibrationPhase.CALIBRATING:
            return
        self.candidates = tuple(candidates)
        self.phase = (
            CalibrationPhase.CHOOSING if self.candidates else CalibrationPhase.FAILED
        )
        self.message = (
            "Choose the surface on which parcels rest. Green pixels mark each candidate."
            if self.candidates
            else "No support plane found. Show an empty horizontal surface, then retry."
        )

    def select(self, generation: int, index: int):
        if generation != self.generation or self.phase is not CalibrationPhase.CHOOSING:
            raise ValueError(
                "These candidates have expired. Use the current calibration."
            )
        if not 0 <= index < len(self.candidates):
            raise ValueError("Unknown support plane candidate.")
        self.plane = self.candidates[index].plane
        self.selected = index
        self.phase = CalibrationPhase.READY
        self.message = "Support plane selected. Place parcels on that surface."


def overlap(a, b):
    left, top = max(a[0], b[0]), max(a[1], b[1])
    right, bottom = min(a[2], b[2]), min(a[3], b[3])
    area = max(0, right - left) * max(0, bottom - top)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - area
    return area / union if union > 0 else 0


@dataclass
class Track:
    bbox: tuple
    center: tuple
    last_seen: float


@dataclass
class ParcelTracker:
    max_age_seconds: float = 2.0
    max_distance_mm: float = 180.0
    next_id: int = 1
    tracks: dict[int, Track] = field(default_factory=dict)

    def clear(self):
        self.tracks.clear()

    def update(self, parcels, now: float):
        self.tracks = {
            key: track
            for key, track in self.tracks.items()
            if now - track.last_seen <= self.max_age_seconds
        }
        matches = []
        for index, parcel in enumerate(parcels):
            for key, track in self.tracks.items():
                distance = math.dist(parcel["center_mm"], track.center)
                iou = overlap(parcel["bbox"], track.bbox)
                if distance <= self.max_distance_mm and (iou >= 0.1 or distance <= 60):
                    matches.append(
                        (distance / self.max_distance_mm + 1 - iou, index, key)
                    )
        assigned, used = {}, set()
        for _, index, key in sorted(matches):
            if index not in assigned and key not in used:
                assigned[index] = key
                used.add(key)
        for index, parcel in enumerate(parcels):
            key = assigned.get(index)
            if key is None:
                key, self.next_id = self.next_id, self.next_id + 1
            self.tracks[key] = Track(
                tuple(parcel["bbox"]), tuple(parcel["center_mm"]), now
            )
            parcel["track_id"] = key
        return parcels
