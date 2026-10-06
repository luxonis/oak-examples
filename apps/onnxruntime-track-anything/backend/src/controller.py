import base64
from collections import deque
import logging
import queue
import threading
import time
import uuid

import cv2
import numpy as np

from model_assets.prepare import MAX_POINTS, ensure_models
from inference.sessions import QnnSessionManager
from inference.mobilesam import MobileSamSelector
from inference.xmem import HEIGHT, WIDTH, XMemTracker

log = logging.getLogger("track-anything")
SELECTION_TTL_SECONDS = 20


class TrackingController:
    """Share camera and UI state while one worker owns all inference sessions.

    Frame packets contain the DepthAI frame, its BGR image, and the host receipt
    time from the monotonic clock. Epochs invalidate work after a target changes.
    """

    def __init__(self):
        self.stop = threading.Event()
        self.lock = threading.RLock()
        self.commands = queue.Queue(maxsize=4)
        self.epoch = 0

        self.latest = None
        self.history = deque(maxlen=120)
        self.result = None
        self.snapshot = None

        self.sessions = None
        self.selector = None
        self.tracker = None
        self.trail = deque(maxlen=60)
        self.last_sequence = -1
        self.update_times = deque(maxlen=30)

        self.state_data = {
            "phase": "loading",
            "ready": False,
            "status": "Starting ONNX Runtime…",
            "error": None,
            "has_frame": False,
            "snapshot_id": None,
            "preview": None,
            "points": [],
            "mask_ready": False,
            "selection_busy": False,
            "selection_ms": None,
            "metrics": {},
            "options": {"mask": True, "outline": True, "box": False, "trail": False},
        }

    def progress(self, message):
        """Log initialization progress and expose it to the frontend."""
        if self.stop.is_set():
            raise InterruptedError("Application stopping")
        log.info(message)
        with self.lock:
            self.state_data["status"] = message

    def state(self, _payload):
        """Return UI state with current frame freshness and selection lifetime."""
        with self.lock:
            result = {
                **self.state_data,
                "options": dict(self.state_data["options"]),
                "has_frame": self.latest is not None
                and time.monotonic() - self.latest[2] < 3,
            }
            result["runtime_error"] = result.pop("error")

            result["selection_remaining_s"] = (
                max(
                    0,
                    SELECTION_TTL_SECONDS
                    - (time.monotonic() - self.snapshot["created"]),
                )
                if self.snapshot and self.state_data["phase"] == "selecting"
                else None
            )
            return result

    def invalidate(self):
        """Discard pending work for older targets; caller must hold the state lock."""
        self.epoch += 1
        while True:
            try:
                self.commands.get_nowait()
            except queue.Empty:
                break

    def action(self, payload):
        """Handle a frontend action, queuing model work for the inference worker.

        Args:
            payload: Action dictionary with action-specific fields. Selection
                edits and tracking start must include the current snapshot ID.

        Returns:
            An acknowledgement, captured-frame data, or an error dictionary.
            Model results are published separately through the state service.
        """
        try:
            if not isinstance(payload, dict):
                raise ValueError("Expected an action object")

            action = payload.get("action")
            if action not in (
                "options",
                "retry",
                "clear",
                "snapshot",
                "points",
                "start",
            ):
                raise ValueError("Unknown action")

            with self.lock:
                if action == "options":
                    for key, value in payload.get("options", {}).items():
                        if key not in self.state_data["options"] or not isinstance(
                            value, bool
                        ):
                            raise ValueError("Unknown visualization option")
                    self.state_data["options"].update(payload["options"])
                    return {"ok": True}

                if (
                    action == "retry"
                    and self.state_data["phase"] == "error"
                    and not self.state_data["ready"]
                ):
                    self.invalidate()
                    self.state_data.update(
                        phase="loading",
                        error=None,
                        status="Retrying model initialization…",
                    )
                    self.commands.put_nowait(("initialize", self.epoch, None))
                    return {"ok": True}

                if action == "clear":
                    if not self.state_data["ready"]:
                        raise ValueError(
                            "Use Retry loading models to recover initialization."
                        )
                    self.invalidate()
                    self.snapshot = self.result = None
                    self.trail.clear()
                    self.state_data.update(
                        phase="idle" if self.state_data["ready"] else "loading",
                        snapshot_id=None,
                        preview=None,
                        points=[],
                        mask_ready=False,
                        selection_busy=False,
                        metrics={},
                        error=None,
                        status="Select an object to begin.",
                    )
                    return {"ok": True}

                if not self.state_data["ready"]:
                    raise ValueError("Wait for the models to finish loading.")
                if self.latest is None or time.monotonic() - self.latest[2] > 3:
                    raise ValueError("Waiting for a fresh camera frame")

                if action == "snapshot":
                    if self.state_data["selection_busy"]:
                        raise ValueError("Wait for the current selection request.")

                    self.invalidate()
                    self.result = None
                    self.trail.clear()
                    packet = self.latest
                    sid = uuid.uuid4().hex
                    self.snapshot = {
                        "id": sid,
                        "packet": packet,
                        "encoded": None,
                        "mask": None,
                        "created": time.monotonic(),
                    }
                    self.state_data.update(
                        phase="selecting",
                        snapshot_id=sid,
                        preview=None,
                        mask_ready=False,
                        points=[],
                        selection_busy=True,
                        error=None,
                        metrics={},
                    )
                    self.commands.put_nowait(("encode", self.epoch, self.snapshot))
                    return {
                        "snapshot_id": sid,
                        "image": data_url(packet[1]),
                        "width": packet[1].shape[1],
                        "height": packet[1].shape[0],
                        "selection_remaining_s": SELECTION_TTL_SECONDS,
                    }

                # Prompt edits and start requests belong to one frozen frame.
                snapshot = self.snapshot
                if not snapshot or payload.get("snapshot_id") != snapshot["id"]:
                    raise ValueError(
                        "Selection is no longer current. Capture a new frame."
                    )
                if time.monotonic() - snapshot["created"] >= SELECTION_TTL_SECONDS:
                    raise ValueError(
                        "Selection expired. Capture an updated frame and select the object again."
                    )
                if self.state_data["selection_busy"]:
                    raise ValueError("Wait for the current selection request.")

                if action == "points":
                    points = validate_points(payload.get("points"))
                    self.state_data.update(
                        selection_busy=True, mask_ready=False, error=None
                    )
                    self.commands.put_nowait(("points", self.epoch, (snapshot, points)))
                elif action == "start":
                    if snapshot["mask"] is None or not snapshot["mask"].any():
                        raise ValueError("Select a visible object first.")
                    self.state_data.update(
                        phase="catching_up", selection_busy=True, error=None
                    )
                    self.commands.put_nowait(("start", self.epoch, snapshot))
                else:
                    raise ValueError("Unknown action")

            return {"ok": True}
        except (ValueError, TypeError, KeyError, queue.Full) as exc:
            return {"error": str(exc) or "The worker is busy. Try again."}

    def capture(self, output):
        """Drain camera output into the latest packet and a bounded 5-Hz history."""
        history_time = 0

        while not self.stop.is_set():
            frame = output.tryGet()
            if frame is None:
                self.stop.wait(0.005)
                continue

            packet = (frame, frame.getCvFrame(), time.monotonic())
            with self.lock:
                self.latest = packet
                if packet[2] - history_time >= 0.2:
                    self.history.append(packet)
                    history_time = packet[2]

    def worker(self):
        """Run model commands and live tracking outside the service callbacks."""
        root = None
        self.commands.put_nowait(("initialize", self.epoch, None))

        while not self.stop.is_set():
            epoch = self.epoch
            try:
                try:
                    action, epoch, value = self.commands.get(timeout=0.005)
                except queue.Empty:
                    action = None

                if epoch != self.epoch:
                    continue

                if action == "initialize":
                    root = ensure_models(self.progress, self.stop)
                    self.tracker = None
                    self.sessions = QnnSessionManager(root, self.progress)
                    self.selector = MobileSamSelector(self.sessions)
                    XMemTracker.load_models(self.sessions)
                    self.selector.load_models()

                    with self.lock:
                        if epoch == self.epoch:
                            self.state_data.update(
                                ready=True,
                                phase="idle",
                                status="Select an object to begin.",
                            )

                elif action == "encode":
                    started = time.perf_counter()
                    encoded = self.selector.encode_selection(value["packet"][1])

                    # Selection may have been cleared while inference was running.
                    with self.lock:
                        if epoch == self.epoch:
                            value["encoded"] = encoded
                            self.state_data.update(
                                selection_busy=False,
                                status="Click the object, or draw a box.",
                                selection_ms=(time.perf_counter() - started) * 1000,
                            )

                elif action == "points":
                    snapshot, points = value
                    started = time.perf_counter()
                    mask, score = self.selector.select(snapshot["encoded"], points)

                    rgba = np.zeros((*mask.shape, 4), np.uint8)
                    rgba[mask] = [160, 220, 25, 110]  # BGRA -> teal
                    preview = data_url(rgba, ".png")

                    with self.lock:
                        if epoch == self.epoch:
                            snapshot["mask"] = mask
                            self.state_data.update(
                                preview=preview,
                                points=points,
                                mask_ready=bool(mask.any()),
                                selection_busy=False,
                                status="Refine the mask or start tracking.",
                                selection_ms=(time.perf_counter() - started) * 1000,
                            )

                elif action == "start":
                    self.tracker = XMemTracker(self.sessions)
                    self.tracker.initialize(value["packet"][1], value["mask"])
                    self.last_sequence = value["packet"][0].getSequenceNum()
                    self.update_times.clear()
                    self.catch_up(epoch)

                    with self.lock:
                        if epoch == self.epoch:
                            self.state_data.update(
                                phase="tracking",
                                selection_busy=False,
                                status="Tracking the selected object.",
                                preview=None,
                            )
                            self.trail.clear()

                else:
                    with self.lock:
                        packet = self.latest
                        tracking = self.state_data["phase"] in ("tracking", "lost")

                    if (
                        tracking
                        and packet
                        and packet[0].getSequenceNum() > self.last_sequence
                    ):
                        self.process(packet, epoch)
            except InterruptedError:
                if self.stop.is_set():
                    return
                raise
            except Exception as exc:
                log.exception("Tracking worker failed")
                with self.lock:
                    if epoch == self.epoch:
                        self.state_data.update(
                            phase="error",
                            error=str(exc),
                            selection_busy=False,
                            status="Operation failed. See the error below.",
                        )
                        self.result = None

    def catch_up(self, epoch):
        """Walk chronological history with bounded effort, then follow latest frames.

        Inference may be slower than history arrival. Terminate after reaching
        the newest available sample, 24 steps, or five seconds; never wait for an
        empty history while the camera keeps producing frames.

        Args:
            epoch: Target generation that owns this catch-up operation.
        """
        deadline = time.monotonic() + 5
        for _ in range(24):
            if self.stop.is_set() or epoch != self.epoch:
                return

            with self.lock:
                pending = [
                    p
                    for p in self.history
                    if p[0].getSequenceNum() > self.last_sequence
                ]
            if not pending:
                return

            # Skip history samples when inference cannot keep up with arrival.
            stride = max(
                1, int(np.ceil(self.tracker.timings.get("inference_ms", 0) / 150))
            )
            self.process(
                pending[min(stride - 1, len(pending) - 1)], epoch, publish=False
            )
            if len(pending) <= stride or time.monotonic() >= deadline:
                return

    def process(self, packet, epoch, publish=True):
        """Track one frame and optionally publish its result, trail, and timings.

        Args:
            packet: Tuple of DepthAI frame, BGR image, and host receipt time.
            epoch: Target generation; stale work must not publish results.
            publish: Whether to update visible state. Catch-up only advances
                the tracker's memory and last processed sequence.
        """
        started = time.perf_counter()
        mask, confidence = self.tracker.step(packet[1])
        self.last_sequence = packet[0].getSequenceNum()
        if not publish:
            return

        yy, xx = np.nonzero(mask)
        now = time.monotonic()
        with self.lock:
            if epoch != self.epoch:
                return

            if len(xx) >= 32:
                self.trail.append((float(xx.mean() / WIDTH), float(yy.mean() / HEIGHT)))
            else:
                self.trail.clear()

            self.update_times.append(now)
            fps = (
                (len(self.update_times) - 1) / (now - self.update_times[0])
                if len(self.update_times) > 1
                else 0
            )

            metrics = {
                **self.tracker.timings,
                "processing_ms": (time.perf_counter() - started) * 1000,
                "frame_age_ms": (now - packet[2]) * 1000,
                "fps": fps,
                "memory_frames": len(self.tracker.memory.entries),
                "sequence": self.last_sequence,
                "mask_pixels": int(len(xx)),
            }

            self.result = (packet[0], mask, confidence, list(self.trail), epoch)
            self.state_data.update(
                phase="tracking" if len(xx) >= 32 else "lost",
                metrics=metrics,
                status="Tracking the selected object."
                if len(xx) >= 32
                else "Target not visible. Reselect if it does not recover.",
            )

        if self.tracker.steps % 30 == 0:
            log.debug(
                "TRACK %s",
                {
                    k: round(v, 2) if isinstance(v, float) else v
                    for k, v in metrics.items()
                },
            )


def data_url(image, extension=".jpg"):
    """Encode an OpenCV image as a JPEG or PNG data URL for the frontend."""
    ok, data = cv2.imencode(extension, image)
    if not ok:
        raise ValueError("Image encoding failed")

    mime = "png" if extension == ".png" else "jpeg"
    return f"data:image/{mime};base64," + base64.b64encode(data).decode()


def validate_points(points):
    """Validate normalized MobileSAM prompts and return canonical point dictionaries.

    Args:
        points: List of dictionaries containing normalized ``x`` and ``y`` values
            and a label: 0 excludes, 1 includes, and 2/3 define box corners.

    Returns:
        Points with float coordinates and integer labels, in their original order.

    Raises:
        ValueError: A coordinate, label, prompt count, or box pair is invalid.
        KeyError: A point is missing a required field.
        TypeError: A point or coordinate cannot be interpreted as expected.
    """
    if not isinstance(points, list) or not 1 <= len(points) <= MAX_POINTS:
        raise ValueError(f"Select between 1 and {MAX_POINTS} points.")

    result = []
    for p in points:
        x, y, label = float(p["x"]), float(p["y"]), p["label"]
        if (
            not np.isfinite([x, y]).all()
            or not 0 <= x <= 1
            or not 0 <= y <= 1
            or label not in (0, 1, 2, 3)
        ):
            raise ValueError("Invalid selection coordinates or point label")
        result.append({"x": x, "y": y, "label": int(label)})

    boxes = [p["label"] for p in result if p["label"] in (2, 3)]
    if boxes and boxes != [2, 3]:
        raise ValueError("A box needs its top-left and bottom-right corners.")
    if not any(p["label"] in (1, 2) for p in result):
        raise ValueError("Include a point on the target first.")

    return result
