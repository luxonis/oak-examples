from collections import OrderedDict, deque
from copy import deepcopy
from datetime import timedelta
import json
from pathlib import Path
import threading
import time

import cv2
import depthai as dai
import numpy as np
from depthai_nodes.message import (
    ParcelDetectorConfig,
    ParcelMeasurements,
    SupportPlaneCalibrationControl,
)

from benchmarks import BenchmarkWindow
from domain import CalibrationPhase, CalibrationSession, ParcelTracker
from geometry import transformed_imu
from rendering import (
    annotated_image,
    candidate_preview,
    metadata_record,
    native_annotations,
    parcel_boxes,
    read_scene,
    stamp,
)


class Command(dai.Buffer):
    def __init__(self, action, payload):
        super().__init__()
        self.action, self.payload = action, payload


class ParcelController(dai.node.ThreadedHostNode):
    def __init__(self, profile, evidence=None):
        super().__init__()
        self.profile = profile
        self.evidence = Path(evidence) if evidence else None
        if self.evidence:
            self.evidence.mkdir(parents=True, exist_ok=True)
        self.events = {
            name: self.createInput(name, blocking=name == "commands", queueSize=size)
            for name, size in (
                ("commands", 16),
                ("calibration", 4),
                ("imu", 4),
                ("detections", 4),
                ("measurements", 4),
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
        self.control = self.createOutput("calibration_control")
        self.config = self.createOutput("detector_config")
        self.video = self.createOutput(
            "video",
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.ImgFrame, True)
            ],
        )
        self.annotations = self.createOutput(
            "annotations",
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.ImgAnnotations, True)
            ],
        )
        self.session, self.tracker = CalibrationSession(), ParcelTracker()
        self.candidates = []
        self.previews = {}
        self.frames = OrderedDict()
        self.pending_detections = {}
        self.pending_measurements = {}
        self.inflight = None
        self.latest_scene = None
        self.last_frame = None
        self.error = None
        self.config_dirty = False
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
            },
            "error": self.error,
            "frame_sequence": self.last_frame["sequence"] if self.last_frame else None,
            "capture": self.profile,
            "rates": self.rates,
            "frame": self.last_frame,
        }
        with self.lock:
            self._snapshot = deepcopy(state)
            self._preview_snapshot = dict(self.previews)

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
                self.candidates = []
                self.previews = {}
                self.control.send(SupportPlaneCalibrationControl.reset())
                self.control.send(SupportPlaneCalibrationControl.start())
            elif message.action == "select":
                self.session.select(
                    message.payload["generation"], message.payload["index"]
                )
                self.config_dirty = True
                if self.evidence:
                    self.session.plane.toJsonFile(self.evidence / "support-plane.json")
            self.error = None
        except ValueError as exception:
            self.error = str(exception)

    def _scene(self, group):
        frame = read_scene(group, self.session.generation)
        first = self.latest_scene is None
        self.latest_scene = frame
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
                "Select a calibrated support plane to enable parcel measurements.",
            )
        elif self.inflight is None:
            finite = frame.points[
                np.isfinite(frame.points).all(axis=1)
                & (np.linalg.norm(frame.points, axis=1) > 0)
            ]
            cloud = stamp(dai.PointCloudData(), frame.cloud)
            cloud.setPoints(finite)
            cloud.setTransformation(frame.cloud.getTransformation())
            if self.config_dirty:
                self.config.send(ParcelDetectorConfig(supportPlane=self.session.plane))
                self.config_dirty = False
            self.inflight = frame.sequence, time.monotonic(), frame
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
        if self.inflight is None or self.inflight[0] != sequence:
            return
        reference = self.inflight[2]
        self.inflight = None
        self.measurement_samples.append(time.monotonic())
        if len(self.measurement_samples) > 1:
            self.rates["measurement_fps"] = (len(self.measurement_samples) - 1) / (
                self.measurement_samples[-1] - self.measurement_samples[0]
            )
        if (
            reference.generation != self.session.generation
            or self.session.phase is not CalibrationPhase.READY
        ):
            return
        parcels = parcel_boxes(detected, reference.projection)
        by_candidate = {item.candidate_id: item for item in measured.items}
        for parcel in parcels:
            item = by_candidate.get(parcel["candidate_id"])
            parcel["status"] = (
                item.status.value if item is not None else "measurement_failed"
            )
            parcel["dimensions_mm"] = (
                [item.cuboid.length_mm, item.cuboid.width_mm, item.cuboid.height_mm]
                if item is not None and item.cuboid
                else None
            )
        parcels = self.tracker.update(parcels, time.monotonic())
        if measured.outcome is ParcelMeasurements.Outcome.FAILED:
            message = (
                f"Frame failed: {measured.failure_code}. No measurement is available."
            )
        elif parcels:
            complete = sum(parcel["status"] == "measured" for parcel in parcels)
            message = (
                f"{len(parcels)} parcels detected, {complete} with complete dimensions."
            )
        else:
            message = "No eligible parcels in view. Keep each parcel fully visible and separated."
        self._display(reference, parcels, message)
        if self.evidence:
            cv2.imwrite(str(self.evidence / "rgb.png"), reference.image)
            cv2.imwrite(
                str(self.evidence / "overlay.png"),
                annotated_image(reference.image, parcels),
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

    def _display(self, frame, parcels, message):
        self.last_frame = {
            "sequence": frame.sequence,
            "video_sequence": frame.color.getSequenceNum(),
            "width": frame.color.getWidth(),
            "height": frame.color.getHeight(),
            "parcels": parcels,
            "message": message,
        }
        self.annotations.send(native_annotations(frame.color, parcels))
        self.video.send(frame.color)

    def _watchdog(self):
        if self._started_at is None:
            return
        if self.latest_scene is None and time.monotonic() - self._started_at > 30:
            raise RuntimeError(
                "No synchronized RGB, mono, and NeuralDepth point cloud arrived within 30 seconds."
            )
        if self.inflight is not None and time.monotonic() - self.inflight[1] > 30:
            raise RuntimeError(
                "Parcel processing did not return a result within 30 seconds."
            )

    def run(self):
        self._started_at = time.monotonic()
        handlers = {
            "commands": self._command,
            "calibration": self._calibration,
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
            for name in ("ParcelDetector", "ParcelDimensioner")
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
                ("detector", "ParcelDetector"),
                ("dimensioner", "ParcelDimensioner"),
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
                    print(json.dumps({"parcel_benchmark": name, **stats}), flush=True)
