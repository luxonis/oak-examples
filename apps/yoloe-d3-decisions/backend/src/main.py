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
from scheduler import choose_track, match_observations, pixel_box, validate_refresh


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
    """Receive each YOLO-E detection batch with its source frame."""

    def __init__(self):
        super().__init__()
        self.app = None

    def build(self, frame, detections, app):
        self.app = app
        self.link_args(frame, detections)
        return self

    def process(self, frame, detections):
        observations = []
        for detection in detections.detections:
            label = int(detection.label)
            observations.append(
                {
                    "label": label,
                    "class_name": getattr(detection, "labelName", "")
                    or self.app.class_name(label),
                    "confidence": float(detection.confidence),
                    "box": [
                        float(detection.xmin),
                        float(detection.ymin),
                        float(detection.xmax),
                        float(detection.ymax),
                    ],
                }
            )
        self.app.observe(frame.getCvFrame(), observations)


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
        self.frame = None
        self.frame_seen = 0.0
        self.history = deque(maxlen=20)
        self.history_revision = 0
        self.completions = deque(maxlen=20)
        self.next_track_id = 1

    def class_name(self, label):
        with self.lock:
            return (
                self.classes[label]
                if 0 <= label < len(self.classes)
                else f"class {label}"
            )

    def observe(self, frame, observations):
        """Pair each detection batch with its exact camera frame.

        Args:
            frame: BGR frame that produced ``observations``.
            observations: Parsed YOLO-E boxes from that frame.
        """
        now = time.monotonic()
        with self.lock:
            paired_frame = frame.copy()
            self.frame = paired_frame
            self.frame_seen = now
            matched, self.next_track_id = match_observations(
                self.tracks,
                observations,
                now,
                self.next_track_id,
            )
            for obs in matched:
                if pixel_box(obs["box"], frame.shape[1], frame.shape[0]) is None:
                    continue
                old = self.tracks.get(obs["id"], {})
                self.tracks[obs["id"]] = {
                    **obs,
                    "frame": paired_frame,
                    "seen": now,
                    "last_started": old.get("last_started", 0),
                    "last_result": old.get("last_result"),
                    "last_completed": old.get("last_completed"),
                }
            for track_id, track in list(self.tracks.items()):
                if now - track["seen"] > 1.5:
                    del self.tracks[track_id]

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
                if questions != self.questions:
                    for track in self.tracks.values():
                        track["last_started"] = 0
                        track["last_result"] = None
                        track["last_completed"] = None
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
                "has_frame": self.frame is not None and now - self.frame_seen < 1.5,
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
                    "actual_per_second": round(len(completions) / 10, 1),
                },
            }
            if (
                not isinstance(message, dict)
                or message.get("history_revision") != self.history_revision
            ):
                state["history"] = list(self.history)
        state["model"] = self.runtime.state()
        return state

    def _next_job(self):
        """Select one due track and keep its source frame with the new job."""
        now = time.monotonic()
        with self.lock:
            if (
                not self.enabled
                or not self.runtime.state()["ready"]
                or self.frame is None
                or now - self.frame_seen > 1.5
            ):
                return None
            track = choose_track(self.tracks, now, self.refresh)
            if track is None:
                return None
            track["last_started"] = now
            job = {
                "id": uuid.uuid4().hex,
                "time": datetime.now(timezone.utc).isoformat(),
                "track_id": track["id"],
                "class_name": track["class_name"],
                "confidence": track["confidence"],
                "box": list(track["box"]),
                "questions": json.loads(json.dumps(self.questions)),
                "state": "running",
                "source_image": None,
                "crop_image": None,
                "result": None,
                "error": None,
            }
            self.history.appendleft(job)
            return job, track["frame"].copy()

    def _infer(self, job, frame):
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
            source_image = jpeg_data_url(marked)
            crop_image = jpeg_data_url(crop)
            with self.lock:
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
                job.update(state="done", result=result)
                track = self.tracks.get(job["track_id"])
                if track:
                    track["last_result"] = result["answers"][0]
                    track["last_completed"] = time.monotonic()
                self.completions.append(time.monotonic())
                self.history_revision += 1
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
                job.update(state="error", error=str(exc))
                self.history_revision += 1
            logger.exception("Decision failed for track %s", job["track_id"])

    def schedule(self):
        """Run one decision at a time, choosing fresh crops on each iteration."""
        while not self.stop.is_set():
            selected = self._next_job()
            if selected is None:
                self.stop.wait(0.1)
                continue
            self._infer(*selected)

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
                frame = camera.requestOutput(
                    size=(640, 640),
                    type=dai.ImgFrame.Type.BGR888i,
                    fps=10,
                )
                # Publish an encoded preview; keep BGR frames for detection and crops.
                video = camera.requestOutput(
                    size=(640, 640),
                    type=dai.ImgFrame.Type.NV12,
                    fps=10,
                )
                encoder = pipeline.create(dai.node.VideoEncoder)
                encoder.setDefaultProfilePreset(
                    fps=10,
                    profile=dai.VideoEncoderProperties.Profile.H264_MAIN,
                )
                video.link(encoder.input)
                self.detector = pipeline.create(NNDetectionNode).build(
                    frame,
                    archive,
                    prompts,
                    self.classes,
                    self.confidence,
                    self.iou,
                )
                pipeline.create(ObservationNode).build(
                    frame, self.detector.detections, self
                )
                remote.addTopic("Video", encoder.out)
                remote.addTopic("Annotations", self.detector.detections_extended)

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
