"""Standalone RVC4 YOLO-E detection and d3-lite crop decisions."""

import json
import logging
import math
import signal
import threading
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

import cv2
import depthai as dai
from box import Box

from decision import validate_questions
from detector.nn_detection_node import NNDetectionNode
from images import jpeg_data_url
from runtime import Runtime
from scheduler import choose_detection, pixel_box, validate_refresh


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
ROOT = Path(__file__).parent
MODEL_YAML = ROOT / "depthai_models/yoloe_v8_l_fp16.RVC4.yaml"
PROMPTS_YAML = ROOT / "detector/prompts_config.yaml"
DEFAULT_QUESTIONS = [
    {
        "type": "noul",
        "instructions": "Is the person wearing a hat?",
        "options": [
            {
                "label": "Yes",
                "description": "A hat is visibly worn on the person's head.",
            },
            {"label": "No", "description": "No hat is visible on the person's head."},
        ],
    }
]


class ObservationNode(dai.node.HostNode):
    """Pair a high-resolution camera frame with tracked detections."""

    def __init__(self):
        super().__init__()
        self.app = None

    def build(self, frame, tracklets, app):
        self.app = app
        self.link_args(frame, tracklets)
        for input_queue in self.getInputs():
            input_queue.setBlocking(False)
            input_queue.setMaxSize(4)
        return self

    def process(self, frame, tracklets):
        """Remap current track boxes to the exact 1080p camera frame."""
        mapped = tracklets.transformTo(frame.getTransformation())
        observations = []
        for tracklet in mapped.tracklets:
            if tracklet.status not in (
                dai.Tracklet.TrackingStatus.NEW,
                dai.Tracklet.TrackingStatus.TRACKED,
            ):
                continue
            detection = tracklet.srcImgDetection
            label = int(tracklet.label)
            roi = tracklet.roi
            if not roi.isNormalized():
                roi = roi.normalize(frame.getWidth(), frame.getHeight())
            observations.append(
                {
                    "id": int(tracklet.id),
                    "label": label,
                    "class_name": getattr(detection, "labelName", "")
                    or self.app.class_name(label),
                    "confidence": float(detection.confidence),
                    "box": [
                        float(roi.x),
                        float(roi.y),
                        float(roi.x + roi.width),
                        float(roi.y + roi.height),
                    ],
                }
            )
        self.app.observe(frame, observations)


class OverlayNode(dai.node.HostNode):
    """Map detector boxes from the letterboxed input onto the encoded video frame."""

    def build(self, frame, detections):
        self.link_args(frame, detections)
        for input_queue in self.getInputs():
            input_queue.setBlocking(False)
            input_queue.setMaxSize(4)
        return self

    def process(self, frame, detections):
        """Publish annotations in the paired 1080p frame's coordinates."""
        self.out.send(detections.transformTo(frame.getTransformation()))


class DecisionApp:
    """Own the detector, decision scheduler, and frontend service state."""

    def __init__(self):
        self.stop = threading.Event()
        self.lock = threading.RLock()
        self.runtime = Runtime(self.stop)
        self.detector = None
        self.classes = ["person"]
        self.confidence = 0.35
        self.iou = 0.5
        self.class_updating = False
        self.detection_error = None
        self.enabled = False
        self.refresh = 2.0
        self.questions = validate_questions(DEFAULT_QUESTIONS)
        self.tracks = {}
        self.frame_seen = 0.0
        self.next_capture_at = 0.0
        self.capture_number = 0
        self.pending_snapshot = None
        self.generation = 0
        self.history = deque(maxlen=20)
        self.history_revision = 0
        self.completions = deque(maxlen=20)

    def class_name(self, label):
        with self.lock:
            return (
                self.classes[label]
                if 0 <= label < len(self.classes)
                else f"class {label}"
            )

    def observe(self, frame, observations):
        """Track detections and retain one paired frame at each capture interval.

        Args:
            frame: DepthAI frame that produced ``observations``.
            observations: Parsed YOLO-E boxes from that frame.
        """
        now = time.monotonic()
        with self.lock:
            self.frame_seen = now
            valid = []
            for obs in observations:
                if pixel_box(obs["box"], frame.getWidth(), frame.getHeight()) is None:
                    continue
                valid.append(obs)
                old = self.tracks.get(obs["id"], {})
                self.tracks[obs["id"]] = {
                    **obs,
                    "seen": now,
                    "last_started": old.get("last_started", 0),
                    "last_result": old.get("last_result"),
                    "last_completed": old.get("last_completed"),
                }
            for track_id, track in list(self.tracks.items()):
                if now - track["seen"] > 1.5:
                    del self.tracks[track_id]

            if self.enabled and not self.class_updating and now >= self.next_capture_at:
                self.next_capture_at = now + self.refresh
                self.capture_number += 1
                # Keep only the latest complete detection/frame pair. The model
                # worker converts the frame to BGR after leaving this callback.
                self.pending_snapshot = (
                    {
                        "frame": frame,
                        "detections": valid,
                        "questions": json.loads(json.dumps(self.questions)),
                        "generation": self.generation,
                        "capture_number": self.capture_number,
                        "time": datetime.now(timezone.utc).isoformat(),
                    }
                    if valid
                    else None
                )

    def detection_config(self, message):
        """Validate and apply YOLO-E classes and thresholds from the UI.

        Args:
            message: Service payload with classes, confidence, and IoU.

        Returns:
            A service acknowledgement or a validation error.
        """
        try:
            if not isinstance(message, dict):
                raise ValueError("Expected detection settings.")
            classes = message.get("classes")
            if not isinstance(classes, list) or not 1 <= len(classes) <= 16:
                raise ValueError("Enter one to sixteen classes.")
            if any(not isinstance(name, str) for name in classes):
                raise ValueError("Every class must be text.")
            classes = [name.strip() for name in classes]
            if (
                not classes
                or any(not name or len(name) > 60 for name in classes)
                or len(set(map(str.casefold, classes))) != len(classes)
            ):
                raise ValueError("Class names must be unique and 1–60 characters.")
            confidence = message.get("confidence")
            iou = message.get("iou")
            if any(
                type(value) not in (int, float)
                or not math.isfinite(value)
                or not 0 <= value <= 1
                for value in (confidence, iou)
            ):
                raise ValueError("Confidence and IoU must be between 0 and 1.")
            with self.lock:
                if self.class_updating:
                    raise ValueError("A class update is already in progress.")
                self.detector.set_confidence_threshold(confidence)
                self.detector.set_iou_threshold(iou)
                self.confidence, self.iou = float(confidence), float(iou)
                if classes != self.classes:
                    self.class_updating = True
                    self.detection_error = None
                    self.generation += 1
                    self.pending_snapshot = None
                    threading.Thread(
                        target=self._update_classes, args=(classes,), daemon=True
                    ).start()
            return {"ok": True}
        except (TypeError, ValueError) as exc:
            return {"error": str(exc)}

    def _update_classes(self, classes):
        try:
            self.detector.update_classes(classes)
            with self.lock:
                self.classes = classes
                self.tracks.clear()
                self.next_capture_at = 0.0
            logger.info("YOLO-E classes changed: %s", classes)
        except Exception as exc:
            with self.lock:
                self.detection_error = str(exc)
            logger.exception("Class update failed")
        finally:
            with self.lock:
                self.class_updating = False

    def decision_config(self, message):
        """Apply question and refresh settings without restarting detection.

        Args:
            message: Service payload containing enablement, refresh, and questions.

        Returns:
            A service acknowledgement or a validation error.
        """
        try:
            if (
                not isinstance(message, dict)
                or type(message.get("enabled")) is not bool
            ):
                raise ValueError("Expected an enabled flag and decision settings.")
            refresh = validate_refresh(message.get("refresh"))
            questions = validate_questions(message.get("questions"))
            with self.lock:
                questions_changed = questions != self.questions
                settings_changed = questions_changed or refresh != self.refresh
                toggled = message["enabled"] != self.enabled
                if questions_changed:
                    for track in self.tracks.values():
                        track["last_started"] = 0
                        track["last_result"] = None
                        track["last_completed"] = None
                if settings_changed or toggled:
                    # Discard a pending snapshot and suppress any in-flight
                    # result from the previous settings or running period.
                    self.generation += 1
                    self.pending_snapshot = None
                    self.next_capture_at = 0.0
                self.enabled = message["enabled"]
                self.refresh = refresh
                self.questions = questions
            return {"ok": True}
        except (TypeError, ValueError) as exc:
            return {"error": str(exc)}

    def state(self, message):
        """Return live UI state, including history only when its revision changes.

        Args:
            message: Poll request with the client's last history revision.

        Returns:
            Current detector, model, track, and decision state.
        """
        now = time.monotonic()
        with self.lock:
            tracks = [
                {
                    key: track[key]
                    for key in ("id", "class_name", "confidence", "box", "last_result")
                }
                | {
                    "decision_age": round(now - track["last_completed"], 1)
                    if track["last_completed"]
                    else None
                }
                for track in self.tracks.values()
                if now - track["seen"] < 1.5
            ]
            completions = [t for t in self.completions if now - t <= 10]
            state = {
                "history_revision": self.history_revision,
                "has_frame": now - self.frame_seen < 1.5,
                "tracks": tracks,
                "detection": {
                    "classes": list(self.classes),
                    "confidence": self.confidence,
                    "iou": self.iou,
                    "updating": self.class_updating,
                    "error": self.detection_error,
                },
                "decision": {
                    "enabled": self.enabled,
                    "refresh": self.refresh,
                    "questions": self.questions,
                    "actual_per_second": round(len(completions) / 10, 1)
                    if self.enabled
                    else 0.0,
                },
            }
            since = (
                message.get("history_revision") if isinstance(message, dict) else None
            )
            if type(since) is not int or since < 0 or since > self.history_revision:
                state["history"] = list(self.history)
                state["history_reset"] = True
            elif since != self.history_revision:
                state["history"] = [
                    job for job in self.history if job["revision"] > since
                ]
                state["history_reset"] = False
        state["model"] = self.runtime.state()
        return state

    def _next_snapshot(self):
        """Take the latest captured detection batch when the model is ready."""
        with self.lock:
            if not self.enabled or not self.runtime.state()["ready"]:
                return None
            snapshot = self.pending_snapshot
            self.pending_snapshot = None
            return snapshot

    def _next_job(self, snapshot):
        """Choose the least recently evaluated crop from one captured frame."""
        with self.lock:
            if (
                not self.enabled
                or snapshot["generation"] != self.generation
                or snapshot["capture_number"] != self.capture_number
                or not snapshot["detections"]
            ):
                return None
            observation = choose_detection(snapshot["detections"], self.tracks)
            snapshot["detections"].remove(observation)
            track = self.tracks.get(observation["id"])
            if track is not None:
                track["last_started"] = time.monotonic()
            job = {
                "id": uuid.uuid4().hex,
                "time": snapshot["time"],
                "track_id": observation["id"],
                "class_name": observation["class_name"],
                "confidence": observation["confidence"],
                "box": list(observation["box"]),
                "questions": snapshot["questions"],
                "state": "done",
                "source_image": None,
                "crop_image": None,
                "result": None,
                "error": None,
            }
            return job

    def _infer(self, job, frame, generation):
        """Evaluate one crop and retain the source image and result for the log.

        Args:
            job: Mutable history entry created by ``_next_job``.
            frame: Frame paired with the selected detection.
        """
        started = time.monotonic()
        try:
            box = pixel_box(job["box"], frame.shape[1], frame.shape[0])
            if box is None:
                raise ValueError("Detection crop is too small or outside the frame.")
            x0, y0, x1, y1 = box
            crop = frame[y0:y1, x0:x1].copy()
            marked = frame.copy()
            cv2.rectangle(marked, (x0, y0), (x1, y1), (0, 180, 255), 3)
            cv2.putText(
                marked,
                f"{job['class_name']} #{job['track_id']}",
                (x0, max(20, y0 - 7)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 180, 255),
                2,
            )
            source_image = jpeg_data_url(marked, max_edge=1920)
            crop_image = jpeg_data_url(crop)
            job["source_image"] = source_image
            job["crop_image"] = crop_image
            prepared = time.monotonic()
            result = self.runtime.decide(
                f"Decide about the detected {job['class_name']} shown in this crop.",
                job["questions"],
                [crop_image],
            )
            result["preparation_ms"] = round((prepared - started) * 1000, 1)
            result["total_ms"] = round((time.monotonic() - started) * 1000, 1)
            with self.lock:
                if not self.enabled or generation != self.generation:
                    return
                job.update(state="done", result=result)
                track = self.tracks.get(job["track_id"])
                if track:
                    track["last_result"] = result["answers"][0]
                    track["last_completed"] = time.monotonic()
                self.completions.append(time.monotonic())
                self.history_revision += 1
                job["revision"] = self.history_revision
                self.history.appendleft(job)
            logger.info(
                "[DECISION] %s",
                json.dumps(
                    {
                        key: job[key]
                        for key in ("id", "track_id", "class_name", "result")
                    }
                ),
            )
        except Exception as exc:
            with self.lock:
                if not self.enabled or generation != self.generation:
                    return
                job.update(state="error", error=str(exc))
                self.history_revision += 1
                job["revision"] = self.history_revision
                self.history.appendleft(job)
            logger.exception("Decision failed for track %s", job["track_id"])

    def schedule(self):
        """Process crops from the latest captured batch in the background."""
        while not self.stop.is_set():
            snapshot = self._next_snapshot()
            if snapshot is None:
                self.stop.wait(0.05)
                continue
            try:
                frame = snapshot["frame"].getCvFrame()
            except Exception:
                logger.exception("Could not read captured decision frame")
                continue
            while (job := self._next_job(snapshot)) is not None:
                self._infer(job, frame, snapshot["generation"])

    def shutdown(self, *_args):
        logger.info("Stopping app")
        self.stop.set()

    def run(self):
        """Build the standalone pipeline and serve its streams and controls."""
        signal.signal(signal.SIGINT, self.shutdown)
        signal.signal(signal.SIGTERM, self.shutdown)
        device = dai.Device()
        if device.getPlatform() != dai.Platform.RVC4:
            device.close()
            raise RuntimeError("This app supports standalone RVC4 only.")

        description = dai.NNModelDescription.fromYamlFile(str(MODEL_YAML))
        description.platform = "RVC4"
        archive = dai.NNArchive(dai.getModelFromZoo(description))
        prompts = Box.from_yaml(filename=str(PROMPTS_YAML))
        remote = dai.RemoteConnection(httpPort=8082)
        remote.registerService("Decision State", self.state)
        remote.registerService("Detection Config", self.detection_config)
        remote.registerService("Decision Config", self.decision_config)

        try:
            with dai.Pipeline(device) as pipeline:
                camera = pipeline.create(dai.node.Camera).build()
                detector_frame = camera.requestOutput(
                    size=(640, 640),
                    type=dai.ImgFrame.Type.BGR888i,
                    resizeMode=dai.ImgResizeMode.LETTERBOX,
                    fps=10,
                )
                # The same 1080p output feeds the encoder and interval-selected crops.
                video = camera.requestOutput(
                    size=(1920, 1080),
                    type=dai.ImgFrame.Type.NV12,
                    fps=10,
                )
                encoder = pipeline.create(dai.node.VideoEncoder)
                encoder.setDefaultProfilePreset(
                    fps=10,
                    profile=dai.VideoEncoderProperties.Profile.H264_MAIN,
                )
                encoder.input.setBlocking(False)
                encoder.input.setMaxSize(1)
                video.link(encoder.input)
                self.detector = pipeline.create(NNDetectionNode).build(
                    detector_frame,
                    archive,
                    prompts,
                    self.classes,
                    self.confidence,
                    self.iou,
                )
                tracker = pipeline.create(dai.node.ObjectTracker)
                tracker.setTrackerType(dai.TrackerType.SHORT_TERM_IMAGELESS)
                tracker.setTrackerIdAssignmentPolicy(
                    dai.TrackerIdAssignmentPolicy.UNIQUE_ID
                )
                tracker.setTrackingPerClass(True)
                tracker.setTrackletBirthThreshold(1)
                tracker.setTrackletMaxLifespan(10)
                detector_frame.link(tracker.inputDetectionFrame)
                detector_frame.link(tracker.inputTrackerFrame)
                self.detector.detections.link(tracker.inputDetections)
                pipeline.create(ObservationNode).build(video, tracker.out, self)
                overlay = pipeline.create(OverlayNode).build(
                    video, self.detector.detections
                )
                remote.addTopic("Video", encoder.out)
                remote.addTopic("Annotations", overlay.out)

                pipeline.start()
                logger.info("Pipeline started.")
                remote.registerPipeline(pipeline)
                threading.Thread(target=self.runtime.start, daemon=True).start()
                threading.Thread(target=self.schedule, daemon=True).start()
                while pipeline.isRunning():
                    if self.stop.is_set():
                        pipeline.stop()
                        break
                    key = remote.waitKey(1)
                    pipeline.processTasks()
                    if key == ord("q"):
                        break
        finally:
            self.stop.set()
            self.runtime.close()


if __name__ == "__main__":
    DecisionApp().run()
