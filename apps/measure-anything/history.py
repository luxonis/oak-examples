import base64
from collections import OrderedDict
from contextlib import closing
from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import threading

import cv2
import depthai as dai
import numpy as np


@dataclass(frozen=True)
class SaveRequest:
    track_id: int
    sequence: int
    request_revision: int | None
    points: np.ndarray
    metadata: dict
    next_track_id: int
    color: dai.ImgFrame | None = None


def object_preview(color, bounds):
    """Decode only the object's active NV12 region, on the storage worker."""
    if color.getType() != dai.ImgFrame.Type.NV12:
        raise ValueError("Measurement previews require an NV12 RGB frame")
    bounds = np.asarray(bounds, dtype=float)
    if bounds.shape != (4,) or not np.isfinite(bounds).all():
        raise ValueError("Measurement preview bounds must be finite XYXY values")
    width, height = color.getWidth(), color.getHeight()
    margin = np.maximum((bounds[2:] - bounds[:2]) * 0.04, 2)
    first = np.maximum(np.floor((bounds[:2] - margin) / 2) * 2, 0).astype(int)
    last = np.minimum(
        np.ceil((bounds[2:] + margin + 1) / 2) * 2, (width, height)
    ).astype(int)
    x1, y1 = first
    x2, y2 = last
    if x2 <= x1 or y2 <= y1 or width % 2 or height % 2:
        raise ValueError("Measurement preview does not intersect the RGB image")
    data, stride = color.getData(), color.getStride()
    luminance = np.ndarray((height, width), np.uint8, buffer=data, strides=(stride, 1))[
        y1:y2, x1:x2
    ]
    chroma = np.ndarray(
        (height // 2, width // 2, 2),
        np.uint8,
        buffer=data,
        offset=color.getPlaneStride(),
        strides=(stride, 2, 1),
    )[y1 // 2 : y2 // 2, x1 // 2 : x2 // 2]
    image = cv2.cvtColorTwoPlane(luminance, chroma, cv2.COLOR_YUV2BGR_NV12)
    scale = min(160 / image.shape[1], 120 / image.shape[0], 1)
    if scale < 1:
        image = cv2.resize(
            image,
            (
                max(1, round(image.shape[1] * scale)),
                max(1, round(image.shape[0] * scale)),
            ),
            interpolation=cv2.INTER_AREA,
        )
    success, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 70])
    if not success:
        raise RuntimeError("Could not encode the measurement preview")
    return base64.b64encode(encoded).decode("ascii")


@dataclass(frozen=True)
class UpdateRequest:
    revision: int
    min_sequence: int


class MeasurementStore:
    LIMIT = 20
    SCHEMA_VERSION = 1

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with closing(self._connect()) as connection, connection:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, self.SCHEMA_VERSION):
                raise RuntimeError(f"Unsupported measurement history schema: {version}")
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS measurements (
                    track_id INTEGER PRIMARY KEY,
                    metadata TEXT NOT NULL,
                    points BLOB NOT NULL,
                    point_count INTEGER NOT NULL,
                    saved_at TEXT NOT NULL,
                    saved_order INTEGER NOT NULL UNIQUE,
                    revision INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS state (
                    name TEXT PRIMARY KEY,
                    value INTEGER NOT NULL
                );
                INSERT OR IGNORE INTO state VALUES ('next_track_id', 1);
                INSERT OR IGNORE INTO state VALUES ('next_saved_order', 1);
                """
            )
            connection.execute(f"PRAGMA user_version={self.SCHEMA_VERSION}")
            self.next_track_id = self._state(connection, "next_track_id")
            self._summaries = self._read_summaries(connection)

    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=5)
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    @staticmethod
    def _state(connection, name):
        return connection.execute(
            "SELECT value FROM state WHERE name=?", (name,)
        ).fetchone()[0]

    @staticmethod
    def _summary(track_id, metadata, point_count, saved_at, revision):
        return {
            "track_id": track_id,
            "saved_at": saved_at,
            "captured_at": metadata["captured_at"],
            "sequence": metadata["sequence"],
            "dimensions_mm": metadata["dimensions_mm"],
            "point_count": point_count,
            "revision": revision,
            "has_preview": bool(metadata.get("preview_jpeg")),
        }

    def _read_summaries(self, connection):
        rows = connection.execute(
            """SELECT track_id, metadata, point_count, saved_at, revision
               FROM measurements ORDER BY saved_order DESC LIMIT ?""",
            (self.LIMIT,),
        ).fetchall()
        return [
            self._summary(track_id, json.loads(metadata), count, saved_at, revision)
            for track_id, metadata, count, saved_at, revision in rows
        ]

    def list_summaries(self):
        with self._lock:
            return deepcopy(self._summaries)

    def save(self, request):
        points = np.asarray(request.points, dtype="<f4")
        if points.ndim != 2 or points.shape[1] != 3 or not np.isfinite(points).all():
            raise ValueError("Measurement points must be finite XYZ rows")
        metadata = dict(request.metadata)
        metadata.update(track_id=request.track_id, sequence=request.sequence)
        if request.color is not None:
            metadata["preview_jpeg"] = object_preview(
                request.color, metadata["bbox_rgb"]
            )
        saved_at = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        self._summary(request.track_id, metadata, len(points), saved_at, 1)
        encoded_metadata = json.dumps(metadata, allow_nan=False, separators=(",", ":"))
        encoded_points = points.tobytes(order="C")
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            previous = connection.execute(
                "SELECT revision FROM measurements WHERE track_id=?",
                (request.track_id,),
            ).fetchone()
            revision = previous[0] + 1 if previous else 1
            saved_order = self._state(connection, "next_saved_order")
            next_track_id = max(
                self._state(connection, "next_track_id"),
                request.next_track_id,
                request.track_id + 1,
            )
            connection.execute(
                """INSERT INTO measurements
                   (track_id, metadata, points, point_count, saved_at, saved_order, revision)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(track_id) DO UPDATE SET
                     metadata=excluded.metadata, points=excluded.points,
                     point_count=excluded.point_count, saved_at=excluded.saved_at,
                     saved_order=excluded.saved_order, revision=excluded.revision""",
                (
                    request.track_id,
                    encoded_metadata,
                    encoded_points,
                    len(points),
                    saved_at,
                    saved_order,
                    revision,
                ),
            )
            connection.execute(
                """DELETE FROM measurements WHERE track_id NOT IN
                   (SELECT track_id FROM measurements ORDER BY saved_order DESC LIMIT ?)""",
                (self.LIMIT,),
            )
            connection.execute(
                "UPDATE state SET value=? WHERE name='next_track_id'", (next_track_id,)
            )
            connection.execute(
                "UPDATE state SET value=? WHERE name='next_saved_order'",
                (saved_order + 1,),
            )
            summaries = self._read_summaries(connection)
        with self._lock:
            self.next_track_id = next_track_id
            self._summaries = summaries

    def detail(self, track_id):
        with closing(
            sqlite3.connect(f"{self.path.resolve().as_uri()}?mode=ro", uri=True)
        ) as connection:
            row = connection.execute(
                """SELECT metadata, points, point_count, saved_at, revision
                   FROM measurements WHERE track_id=?""",
                (track_id,),
            ).fetchone()
        if row is None:
            raise KeyError("This measurement is no longer in the last 20 objects.")
        metadata, points, point_count, saved_at, revision = row
        metadata = json.loads(metadata)
        return {
            **metadata,
            **self._summary(track_id, metadata, point_count, saved_at, revision),
            "point_cloud": {
                "encoding": "float32-le-base64",
                "count": point_count,
                "xyz": base64.b64encode(points).decode("ascii"),
            },
        }

    def preview(self, track_id, revision):
        with closing(
            sqlite3.connect(f"{self.path.resolve().as_uri()}?mode=ro", uri=True)
        ) as connection:
            row = connection.execute(
                "SELECT metadata, revision FROM measurements WHERE track_id=?",
                (track_id,),
            ).fetchone()
        if row is None:
            raise KeyError("This measurement is no longer in the last 20 objects.")
        metadata, current_revision = row
        if revision != current_revision:
            raise KeyError("This measurement has been updated. Refresh its preview.")
        return {"jpeg": json.loads(metadata).get("preview_jpeg")}


class SaveScheduler:
    def __init__(self, known_saved=()):
        self.known_saved = set(known_saved)
        self.pending_updates = OrderedDict()
        self.waiting = OrderedDict()
        self.busy = None
        self.last_submitted_sequence = -1
        self.errors = {}
        self._revision = 0

    @property
    def error(self):
        return next(reversed(self.errors.values()), None)

    def request_update(self, track_id, min_sequence):
        if track_id not in self.pending_updates:
            self._revision += 1
            self.pending_updates[track_id] = UpdateRequest(self._revision, min_sequence)
        self.errors.pop(track_id, None)

    def reset_visibility(self, visible):
        for track_id in list(self.waiting):
            if track_id not in visible:
                self.waiting.pop(track_id)
        for track_id in list(self.pending_updates):
            if track_id not in visible:
                self.pending_updates.pop(track_id)
                self.errors[track_id] = "Object not in frame"

    def choose(self, sequence, eligible):
        for track_id in eligible:
            if track_id not in self.known_saved and track_id not in self.errors:
                self.waiting.setdefault(track_id, None)
        if self.busy is not None or sequence <= self.last_submitted_sequence:
            return None
        for track_id, update in self.pending_updates.items():
            if track_id in eligible and sequence > update.min_sequence:
                self.busy = replace(
                    eligible[track_id], request_revision=update.revision
                )
                break
        else:
            self.busy = next(
                (
                    eligible[track_id]
                    for track_id in self.waiting
                    if track_id in eligible
                    and track_id not in self.known_saved
                    and track_id not in self.pending_updates
                    and track_id not in self.errors
                ),
                None,
            )
        if self.busy is not None:
            self.last_submitted_sequence = sequence
        return self.busy

    def complete(self, request, error=None):
        if self.busy is None or (
            self.busy.track_id,
            self.busy.sequence,
            self.busy.request_revision,
        ) != (request.track_id, request.sequence, request.request_revision):
            return
        self.busy = None
        self.waiting.pop(request.track_id, None)
        update = self.pending_updates.get(request.track_id)
        if update and update.revision == request.request_revision:
            self.pending_updates.pop(request.track_id)
        if error is None:
            self.known_saved.add(request.track_id)
            self.errors.pop(request.track_id, None)
        else:
            self.errors[request.track_id] = str(error)
