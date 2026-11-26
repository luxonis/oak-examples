from collections import OrderedDict, deque
from copy import deepcopy
from datetime import timedelta
import json
from pathlib import Path
import sqlite3
import threading
import time

import cv2
import depthai as dai
import numpy as np
from depthai_nodes.message import (
    MeasureAnythingDetectorConfig,
    MeasureAnythingMeasurements,
    SupportPlaneCalibrationControl,
)

from benchmarks import BenchmarkWindow
from domain import CalibrationPhase, CalibrationSession, ObjectTracker
from geometry import transformed_imu
from history import SaveScheduler
from preview import PreviewRequest
from rendering import (
    annotated_image,
    candidate_preview,
    metadata_record,
    native_annotations,
    object_boxes,
    read_scene,
    stamp,
)
from snapshot import measurement_snapshot
from storage_node import SaveMessage


class Command(dai.Buffer):
    def __init__(self, action, payload):
        super().__init__()
        self.action, self.payload = action, payload


class MeasurementController(dai.node.ThreadedHostNode):
    def __init__(self, profile, evidence=None, store=None):
        super().__init__()
        self.profile = profile
        self.store = store
        self.evidence = Path(evidence) if evidence else None
        if self.evidence:
            self.evidence.mkdir(parents=True, exist_ok=True)
        self.events = {
            name: self.createInput(name, blocking=name == "commands", queueSize=size)
            for name, size in (
                ("commands", 16),
                ("calibration", 4),
                ("verification", 2),
                ("imu", 4),
                ("detections", 4),
                ("measurements", 4),
                ("saved", 2),
                ("scene", 2),
            )
        }
        self._commands = self.events["commands"].createInputQueue(
            maxSize=16, blocking=True
        )
        self.detector_streams = {
            name: self.createOutput(name)
            for name in ("cloud", "color", "left", "right")
        }
        self.imu = self.createOutput("calibrated_imu")
        self.calibration_cloud = self.createOutput("organized_calibration_cloud")
        self.control = self.createOutput("calibration_control")
        self.config = self.createOutput("detector_config")
        self.history_jobs = self.createOutput("history_jobs")
        self.preview_jobs = self.createOutput("preview_jobs")
        self.session, self.tracker = CalibrationSession(), ObjectTracker()
        self.scheduler = SaveScheduler(
            known_saved=[row["track_id"] for row in store.list_summaries()]
            if store
            else ()
        )
        if store:
            self.tracker.next_id = store.next_track_id
        self.overlays = {"depth": False, "support_plane": False}
        self.visible_tracks = set()
        self.last_measurement_at = None
        self._history_snapshot = {}
        self.candidates = []
        self.previews = {}
        self.frames = OrderedDict()
        self.pending_detections = {}
        self.pending_measurements = {}
        self.inflight = OrderedDict()
        self.last_result_sequence = -1
        self.latest_scene = None
        self.last_frame = None
        self.axial_correction = None
        self.error = None
        self.config_dirty = False
        self.verification = None
        self.pending_verification = None
        self.next_verification_at = 0.0
        self.capture_samples = deque(maxlen=60)
        self.measurement_samples = deque(maxlen=30)
        self.rates = {"source_fps": None, "measurement_fps": None}
        self.lock = threading.Lock()
        self._snapshot = {}
        self._preview_snapshot = {}
        self._started_at = None
        self._publish_state()

    def _publish_state(self):
        state = {
            "calibration": {
                "phase": self.session.phase.value,
                "generation": self.session.generation,
                "message": self.session.message,
                "selected": self.session.selected,
                "plane": self.session.plane.toJson() if self.session.plane else None,
                "candidates": self.candidates,
                "recalibration_required": self.session.recalibration_required,
                "verification": self.verification,
            },
            "error": self.error,
            "frame_sequence": self.last_frame["sequence"] if self.last_frame else None,
            "capture": self.profile,
            "rates": self.rates,
            "frame": self.last_frame,
            "overlays": dict(self.overlays),
            "depth_correction": self.axial_correction,
        }
        visible = self._current_visible()
        active = self._current_active()
        history = {
            "items": [
                dict(
                    row,
                    in_frame=row["track_id"] in visible,
                    track_active=row["track_id"] in active,
                )
                for row in self.store.list_summaries()
            ]
            if self.store
            else [],
            "saving_track_id": self.scheduler.busy.track_id
            if self.scheduler.busy
            else None,
            "pending_track_ids": list(self.scheduler.pending_updates),
            "storage_error": self.scheduler.error,
        }
        with self.lock:
            self._snapshot = deepcopy(state)
            self._preview_snapshot = dict(self.previews)
            self._history_snapshot = history

    def _current_visible(self):
        if (
            self.session.phase is not CalibrationPhase.READY
            or self.last_measurement_at is None
            or time.monotonic() - self.last_measurement_at
            > self.tracker.max_age_seconds
        ):
            return set()
        return self.visible_tracks

    def _current_active(self):
        self.tracker.expire(time.monotonic())
        if self.session.phase is not CalibrationPhase.READY:
            return set()
        return {
            track_id
            for track_id, track in self.tracker.tracks.items()
            if track.confirmed
        }

    @staticmethod
    def _track_id(payload):
        if (
            not isinstance(payload, dict)
            or isinstance(payload.get("track_id"), bool)
            or not isinstance(payload.get("track_id"), int)
            or payload["track_id"] < 1
        ):
            raise ValueError("track_id must be a positive integer.")
        return payload["track_id"]

    def get_measurements(self, _payload):
        with self.lock:
            return deepcopy(self._history_snapshot)

    def get_measurement(self, payload):
        try:
            track_id = self._track_id(payload)
            if self.store is None:
                raise ValueError("Measurement storage is unavailable.")
            record = self.store.detail(track_id)
            if record is None:
                raise ValueError(
                    "This measurement is no longer in the latest 20 objects."
                )
            return {"measurement": record}
        except (
            KeyError,
            ValueError,
            OSError,
            RuntimeError,
            sqlite3.Error,
        ) as exception:
            return {"error": str(exception)}

    def update_measurement(self, payload):
        try:
            track_id = self._track_id(payload)
        except ValueError as exception:
            return {"error": str(exception)}
        history = self.get_measurements({})
        if not any(
            row["track_id"] == track_id and row["track_active"]
            for row in history["items"]
        ):
            return {"error": "Object not in frame."}
        return self._enqueue("update_measurement", {"track_id": track_id})

    def get_measurement_preview(self, payload):
        try:
            track_id = self._track_id(payload)
            revision = payload.get("revision")
            if (
                isinstance(revision, bool)
                or not isinstance(revision, int)
                or revision < 1
            ):
                raise ValueError("revision must be a positive integer.")
            if self.store is None:
                raise ValueError("Measurement storage is unavailable.")
            return self.store.preview(track_id, revision)
        except (
            KeyError,
            ValueError,
            OSError,
            RuntimeError,
            sqlite3.Error,
        ) as exception:
            return {"error": str(exception)}

    def set_preview_options(self, payload):
        if (
            not isinstance(payload, dict)
            or set(payload) != {"depth", "support_plane"}
            or any(not isinstance(value, bool) for value in payload.values())
        ):
            return {"error": "depth and support_plane must be booleans."}
        return self._enqueue("preview_options", payload)

    def get_state(self, _payload):
        with self.lock:
            return deepcopy(self._snapshot)

    def calibrate(self, payload):
        if not isinstance(payload, dict):
            return {"error": "Expected an object."}
        return self._enqueue("calibrate", {})

    def select(self, payload):
        if not isinstance(payload, dict) or any(
            isinstance(payload.get(key), bool) or not isinstance(payload.get(key), int)
            for key in ("generation", "index")
        ):
            return {"error": "generation and index must be integers."}
        return self._enqueue("select", payload)

    def preview(self, payload):
        if not isinstance(payload, dict) or any(
            isinstance(payload.get(key), bool) or not isinstance(payload.get(key), int)
            for key in ("generation", "index")
        ):
            return {"error": "generation and index must be integers."}
        with self.lock:
            key = payload["generation"], payload["index"]
            image = self._preview_snapshot.get(key)
        return {"jpeg": image} if image else {"error": "This preview has expired."}

    def _enqueue(self, action, payload):
        try:
            self._commands.send(Command(action, dict(payload)))
        except RuntimeError as exception:
            return {"error": str(exception)}
        return {"ok": True}

    def _command(self, message):
        try:
            if message.action == "calibrate":
                self.session.start()
                self.tracker.clear()
                self.visible_tracks.clear()
                self.scheduler.retain_tracks(set())
                self.candidates = []
                self.previews = {}
                self.verification = None
                self.measurement_samples.clear()
                self.rates["measurement_fps"] = None
                self.control.send(SupportPlaneCalibrationControl.reset())
                self.control.send(SupportPlaneCalibrationControl.start())
            elif message.action == "select":
                self.session.select(
                    message.payload["generation"], message.payload["index"]
                )
                self.config_dirty = True
                self.verification = None
                self.next_verification_at = time.monotonic() + 5
                if self.evidence:
                    self.session.plane.toJsonFile(self.evidence / "support-plane.json")
            elif message.action == "preview_options":
                self.overlays = dict(message.payload)
                if self.overlays["support_plane"]:
                    self.overlays["depth"] = False
                    self.overlays["support_plane"] = self.session.plane is not None
            elif message.action == "update_measurement":
                track_id = message.payload["track_id"]
                if track_id in self._current_active():
                    self.scheduler.request_update(track_id, self.latest_scene.sequence)
            self.error = None
        except ValueError as exception:
            self.error = str(exception)

    def _scene(self, group):
        frame = read_scene(group, self.session.generation)
        first = self.latest_scene is None
        self.latest_scene = frame
        self.axial_correction = frame.axial_correction
        if first:
            print(json.dumps({"depth_correction": self.axial_correction}), flush=True)
        self.calibration_cloud.send(frame.cloud)
        self.frames[frame.sequence] = frame
        while len(self.frames) > 24:
            self.frames.popitem(last=False)
        self.capture_samples.append(
            (
                frame.color.getSequenceNum(),
                frame.color.getTimestampDevice().total_seconds(),
            )
        )
        if len(self.capture_samples) > 1:
            elapsed = self.capture_samples[-1][1] - self.capture_samples[0][1]
            if elapsed > 0:
                self.rates["source_fps"] = (
                    self.capture_samples[-1][0] - self.capture_samples[0][0]
                ) / elapsed
        if first and self.evidence:
            (self.evidence / "camera-calibration.json").write_text(
                json.dumps(
                    {
                        "capture_profile": self.profile,
                        "streams": {
                            name: metadata_record(group[name])
                            for name in (
                                "pointCloud",
                                "color",
                                "left",
                                "right",
                                "depth",
                            )
                        },
                    },
                    indent=2,
                )
            )
        if self.session.phase is not CalibrationPhase.READY:
            self._display(
                frame,
                [],
                "Select a calibrated support plane to enable object measurements.",
            )
        elif len(self.inflight) < 2:
            finite = frame.points[
                np.isfinite(frame.points).all(axis=1)
                & (np.linalg.norm(frame.points, axis=1) > 0)
            ]
            cloud = stamp(dai.PointCloudData(), frame.cloud)
            cloud.setPoints(finite)
            cloud.setTransformation(frame.cloud.getTransformation())
            if self.config_dirty:
                self.config.send(
                    MeasureAnythingDetectorConfig(supportPlane=self.session.plane)
                )
                self.config_dirty = False
            self.inflight[frame.sequence] = time.monotonic(), frame
            for name, message in (
                ("color", frame.color),
                ("left", frame.left),
                ("right", frame.right),
                ("cloud", cloud),
            ):
                self.detector_streams[name].send(message)

    def _imu(self, message):
        if self.latest_scene is not None:
            color_pose = np.linalg.inv(self.latest_scene.projection.reference_to_camera)
            self.imu.send(transformed_imu(message, color_pose[:3, :3]))

    def _calibration(self, result):
        if self.session.phase is not CalibrationPhase.CALIBRATING:
            return
        self.session.finish(result.candidates)
        reference = self.frames.get(result.getSequenceNum()) or self.latest_scene
        best = max(
            (candidate.inlier_count for candidate in result.candidates), default=0
        )
        self.candidates = [
            {
                "index": index,
                "plane": candidate.plane.toJson(),
                "inlier_count": candidate.inlier_count,
                "inlier_ratio": candidate.inlier_ratio,
                "recommended": candidate.inlier_count == best,
            }
            for index, candidate in enumerate(result.candidates)
        ]
        self.previews = {
            (self.session.generation, index): candidate_preview(
                reference, candidate.plane
            )
            for index, candidate in enumerate(result.candidates)
            if reference is not None
        }
        print(
            json.dumps(
                {"calibration": self.session.phase.value, "candidates": self.candidates}
            ),
            flush=True,
        )

    def _detections(self, batch):
        self.pending_detections[batch.getSequenceNum()] = batch
        self._complete(batch.getSequenceNum())

    def _verify_due(self, now):
        if (
            self.session.phase is CalibrationPhase.READY
            and self.latest_scene is not None
            and self.pending_verification is None
            and now >= self.next_verification_at
        ):
            self.pending_verification = (
                self.session.generation,
                self.session.plane,
                self.latest_scene.sequence,
            )
            self.next_verification_at = now + 5
            self.control.send(SupportPlaneCalibrationControl.verify(self.session.plane))

    def _verification(self, result):
        pending = self.pending_verification
        if pending is None:
            return
        self.pending_verification = None
        generation, plane, minimum_sequence = pending
        if (
            generation != self.session.generation
            or self.session.phase is not CalibrationPhase.READY
            or self.session.plane.toJson() != plane.toJson()
            or result.plane.toJson() != plane.toJson()
        ):
            return
        if result.getSequenceNum() < minimum_sequence:
            self.next_verification_at = 0
            return
        self.verification = {
            "accepted": result.accepted,
            "gravity_angle_deg": result.gravity_angle_deg,
            "on_plane_ratio": result.on_plane_ratio,
            "sequence": result.getSequenceNum(),
        }
        print(json.dumps({"support_plane_verification": self.verification}), flush=True)
        if result.accepted:
            return
        self.session.invalidate(
            "The support plane no longer matches the scene or gravity. "
            "Measurements are paused. Keep the camera fixed and recalibrate the support surface."
        )
        self.tracker.clear()
        self.visible_tracks.clear()
        self.last_measurement_at = None
        self.measurement_samples.clear()
        self.rates["measurement_fps"] = None
        self.scheduler.retain_tracks(set())
        self.candidates = []
        self.previews = {}
        self.last_frame = None
        self.config_dirty = False
        self.overlays["support_plane"] = False

    def _measurements(self, batch):
        self.pending_measurements[batch.getSequenceNum()] = batch
        self._complete(batch.getSequenceNum())

    def _complete(self, sequence):
        if (
            sequence not in self.pending_detections
            or sequence not in self.pending_measurements
        ):
            return
        detected = self.pending_detections.pop(sequence)
        measured = self.pending_measurements.pop(sequence)
        if sequence not in self.inflight:
            return
        _, reference = self.inflight.pop(sequence)
        if (
            reference.generation != self.session.generation
            or self.session.phase is not CalibrationPhase.READY
            or sequence <= self.last_result_sequence
        ):
            return
        self.last_result_sequence = sequence
        self.measurement_samples.append(time.monotonic())
        if len(self.measurement_samples) > 1:
            self.rates["measurement_fps"] = (len(self.measurement_samples) - 1) / (
                self.measurement_samples[-1] - self.measurement_samples[0]
            )
        objects = object_boxes(detected, reference.projection)
        by_candidate = {item.candidate_id: item for item in measured.items}
        for detected_object in objects:
            item = by_candidate.get(detected_object["candidate_id"])
            detected_object["status"] = (
                item.status.value if item is not None else "measurement_failed"
            )
            detected_object["dimensions_mm"] = (
                [item.cuboid.length_mm, item.cuboid.width_mm, item.cuboid.height_mm]
                if item is not None and item.cuboid
                else None
            )
        objects = [
            detected_object
            for detected_object in self.tracker.update(objects, time.monotonic())
            if self.tracker.is_confirmed(detected_object["track_id"])
        ]
        self.last_measurement_at = time.monotonic()
        self.visible_tracks = {
            detected_object["track_id"] for detected_object in objects
        }
        self.scheduler.retain_tracks(self._current_active())
        if self.store is not None and self.scheduler.busy is None:
            eligible = {
                detected_object["track_id"]: measurement_snapshot(
                    detected_object,
                    detected,
                    measured,
                    reference,
                    self.profile,
                    self.tracker.next_id,
                )
                for detected_object in objects
                if detected_object["status"] == "measured"
                and detected_object["track_id"] not in self.scheduler.errors
                and (
                    detected_object["track_id"] not in self.scheduler.known_saved
                    or detected_object["track_id"] in self.scheduler.pending_updates
                )
            }
            request = self.scheduler.choose(sequence, eligible)
            if request is not None:
                self.history_jobs.send(SaveMessage(request))
        if measured.outcome is MeasureAnythingMeasurements.Outcome.FAILED:
            message = (
                f"Frame failed: {measured.failure_code}. No measurement is available."
            )
        elif objects:
            complete = sum(
                detected_object["status"] == "measured" for detected_object in objects
            )
            message = (
                f"{len(objects)} objects detected, {complete} with complete dimensions."
            )
        else:
            message = "No eligible objects in view. Keep each object fully visible and separated."
        self._display(reference, objects, message)
        if self.evidence:
            cv2.imwrite(str(self.evidence / "rgb.png"), reference.image)
            cv2.imwrite(
                str(self.evidence / "overlay.png"),
                annotated_image(reference.image, objects),
            )
            (self.evidence / "latest.json").write_text(
                json.dumps(
                    {
                        "state": self._state_data(),
                        "frame": self.last_frame,
                        "outcome": measured.outcome.value,
                        "failure_code": measured.failure_code,
                        "measurement_plane": measured.plane.toJson()
                        if measured.plane is not None
                        else None,
                        "algorithm_id": measured.algorithm_id,
                    },
                    indent=2,
                )
            )

    def _state_data(self):
        self._publish_state()
        return self.get_state({})

    def _saved(self, acknowledgement):
        self.scheduler.complete(acknowledgement.request, acknowledgement.error)

    def _display(self, frame, objects, message):
        self.last_frame = {
            "sequence": frame.sequence,
            "video_sequence": frame.color.getSequenceNum(),
            "width": frame.color.getWidth(),
            "height": frame.color.getHeight(),
            "objects": objects,
            "message": message,
        }
        self.preview_jobs.send(
            PreviewRequest(
                frame,
                depth=self.overlays["depth"],
                plane=self.session.plane if self.overlays["support_plane"] else None,
                annotations=native_annotations(frame.color, objects),
            )
        )

    def _watchdog(self):
        self.scheduler.retain_tracks(self._current_active())
        self._verify_due(time.monotonic())
        if self._started_at is None:
            return
        if self.latest_scene is None and time.monotonic() - self._started_at > 30:
            raise RuntimeError(
                "No synchronized RGB, mono, and depth point cloud arrived within 30 seconds."
            )
        if (
            self.inflight
            and time.monotonic() - next(iter(self.inflight.values()))[0] > 30
        ):
            raise RuntimeError(
                "Object processing did not return a result within 30 seconds."
            )

    def run(self):
        self._started_at = time.monotonic()
        handlers = {
            "commands": self._command,
            "saved": self._saved,
            "calibration": self._calibration,
            "verification": self._verification,
            "imu": self._imu,
            "detections": self._detections,
            "measurements": self._measurements,
            "scene": self._scene,
        }
        try:
            while self.isRunning():
                events = dai.MessageQueue.getAny(self.events, timedelta(seconds=1))
                for name, handler in handlers.items():
                    if name in events:
                        handler(events[name])
                self._watchdog()
                self._publish_state()
        except Exception as exception:
            if self.isRunning():
                self.error = str(exception)
                self._publish_state()
                raise


class BenchmarkLogger(dai.node.ThreadedHostNode):
    def __init__(self):
        super().__init__()
        self.events = {
            name: self.createInput(name, queueSize=256)
            for name in (
                "detector_message",
                "dimensioner_message",
                "detector_report",
                "dimensioner_report",
            )
        }

    def run(self):
        windows = {
            name: BenchmarkWindow(time.monotonic())
            for name in ("MeasureAnythingDetector", "MeasureAnythingDimensioner")
        }
        while self.isRunning():
            remaining = max(
                0,
                min(
                    window.started_at + window.interval_seconds
                    for window in windows.values()
                )
                - time.monotonic(),
            )
            events = dai.MessageQueue.getAny(self.events, timedelta(seconds=remaining))
            for prefix, name in (
                ("detector", "MeasureAnythingDetector"),
                ("dimensioner", "MeasureAnythingDimensioner"),
            ):
                message = events.get(prefix + "_message")
                if message is not None:
                    windows[name].record_message(
                        failed=message.outcome.value == "failed"
                    )
                report = events.get(prefix + "_report")
                if report is not None:
                    windows[name].add_report(
                        int(report.numMessagesReceived), report.averageLatency
                    )
                stats = windows[name].report(time.monotonic())
                if stats is not None:
                    print(
                        json.dumps({"measurement_benchmark": name, **stats}), flush=True
                    )
