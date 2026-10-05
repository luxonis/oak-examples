import json
import logging as log
import signal
import threading
import time
import uuid
from collections import OrderedDict, deque

import depthai as dai

from images import jpeg_data_url, prepare_image
from constants import load_config, validate_max_tokens, validate_temperature
from runtime import Runtime


log.basicConfig(level=log.INFO)
logger = log.getLogger(__name__)


class VlmApp:
    """Coordinate camera capture, frontend services, and VLM inference."""

    def __init__(self):
        # Shared shutdown signal for the main loop and background workers.
        self.stop = threading.Event()

        # Protect frames, snapshots, and jobs shared with frontend service callbacks.
        self.lock = threading.Lock()
        self.frame = None
        self.frame_time = 0
        self.snapshots = OrderedDict()
        self.job = None
        self.history = deque(maxlen=3)

        config = load_config()
        self.default_max_tokens = config["generation"]["max_tokens"]
        self.default_temperature = config["generation"]["temperature"]
        self.image_size = config["image"]["max_edge"]
        self.runtime = Runtime(self.stop, config)

    def capture(self, queue):
        """Update the latest camera frame in a worker until shutdown is requested."""
        while not self.stop.is_set():
            message = queue.tryGet()
            if message is None:
                self.stop.wait(0.01)
                continue

            frame = message.getCvFrame()
            with self.lock:
                self.frame = frame
                self.frame_time = time.monotonic()

    def snapshot(self, _message):
        """Retain a full-resolution frame for region selection.

        Args:
            _message: Unused frontend service payload.

        Returns:
            A dictionary with snapshot ID, JPEG data URL, and pixel dimensions,
            or an error message if no fresh camera frame is available.
        """
        with self.lock:
            if self.frame is None or time.monotonic() - self.frame_time > 3:
                return {"error": "Waiting for a fresh camera frame."}

            # Keep the exact full-resolution frame shown in the selection preview.
            frame = self.frame.copy()
            snapshot_id = uuid.uuid4().hex
            self.snapshots[snapshot_id] = (frame, time.monotonic())

            while len(self.snapshots) > 4:
                self.snapshots.popitem(last=False)

        # JPEG encoding can run after releasing the shared-state lock.
        return {
            "snapshot_id": snapshot_id,
            "image": jpeg_data_url(frame),
            "width": frame.shape[1],
            "height": frame.shape[0],
        }

    def state(self, _message):
        """Return copies of the current job and recent history, plus model status."""
        with self.lock:
            state = {
                "job": dict(self.job) if self.job else None,
                "history": [dict(job) for job in self.history],
                "has_frame": self.frame is not None
                and time.monotonic() - self.frame_time < 3,
                "image_size": self.image_size,
                "default_max_tokens": self.default_max_tokens,
                "default_temperature": self.default_temperature,
            }

        state["model"] = self.runtime.state()
        return state

    def submit(self, message):
        """Validate and accept a request, then start inference in a worker.

        Args:
            message: Dictionary containing prompt and optional max_tokens and
                temperature overrides. A normalized region requires snapshot_id;
                without a region, the latest camera frame is used.

        Returns:
            A dictionary with the accepted job ID, or an error message for an
            invalid request, unavailable model/frame, or busy inference worker.
        """
        try:
            if not isinstance(message, dict):
                raise ValueError("Expected a prompt request.")

            # Validate request settings before reserving the single inference slot.
            prompt = message.get("prompt", "")
            max_tokens = validate_max_tokens(
                message.get("max_tokens", self.default_max_tokens)
            )
            temperature = validate_temperature(
                message.get("temperature", self.default_temperature)
            )
            if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 2000:
                raise ValueError("Enter a prompt between 1 and 2000 characters.")

            if not self.runtime.state()["ready"]:
                raise ValueError("The model is not ready yet.")

            region = message.get("region")
            snapshot_id = message.get("snapshot_id")

            # Check availability and publish the new job under the same lock.
            with self.lock:
                if self.job and self.job["state"] in ("preparing", "running"):
                    raise ValueError(
                        "An inference is already running. Wait for it to finish."
                    )

                # A region uses its saved snapshot; full-frame mode uses the latest frame.
                if region is not None:
                    snapshot = (
                        self.snapshots.get(snapshot_id)
                        if isinstance(snapshot_id, str)
                        else None
                    )
                    if snapshot is None or time.monotonic() - snapshot[1] > 300:
                        raise ValueError("Selection expired. Capture a new snapshot.")
                    frame = snapshot[0].copy()
                else:
                    if self.frame is None or time.monotonic() - self.frame_time > 3:
                        raise ValueError("Waiting for a fresh camera frame.")
                    frame = self.frame.copy()

                # Validate and prepare before accepting the request.
                prepared = prepare_image(frame, region, self.image_size)
                image = jpeg_data_url(prepared)

                job_id = uuid.uuid4().hex
                self.job = {
                    "id": job_id,
                    "state": "preparing",
                    "prompt": prompt.strip(),
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "text": "",
                    "mode": "region" if region is not None else "full",
                    "error": None,
                    "ttft_ms": None,
                    "total_ms": None,
                    "finish_reason": None,
                    "input_image": image,
                    "input_width": prepared.shape[1],
                    "input_height": prepared.shape[0],
                }

                # Keep the three latest requests in memory, including streamed updates.
                self.history.appendleft(self.job)

            # Return immediately so frontend polling stays responsive during generation.
            threading.Thread(
                target=self.infer,
                args=(prompt.strip(), image, max_tokens, temperature),
                daemon=True,
            ).start()
            return {"id": job_id}

        except (ValueError, TypeError) as exc:
            return {"error": str(exc)}

    def infer(self, prompt, image, max_tokens, temperature):
        """Stream into the accepted job, storing failures in its error field."""

        # Publish answer text and its timings together for frontend polling.
        def update(text, first, last):
            with self.lock:
                self.job.update(
                    text=text, ttft_ms=round(first, 1), total_ms=round(last, 1)
                )

        try:
            with self.lock:
                self.job["state"] = "running"

            # The model request runs without holding the shared-state lock.
            result = self.runtime.generate(
                prompt, image, update, max_tokens=max_tokens, temperature=temperature
            )

            with self.lock:
                self.job.update(result, state="done")
                evidence = {
                    key: value
                    for key, value in self.job.items()
                    if key != "input_image"
                }

            logger.info("[RESULT] %s", json.dumps(evidence))

        except Exception as exc:
            with self.lock:
                self.job.update(state="error", error=str(exc))
            logger.error("[inference] %s", exc)

    def _handle_shutdown_signal(self, _signum, _frame):
        """Request shutdown of the pipeline and background workers."""
        logger.info("Application received a stop signal. Stopping the app...")
        self.stop.set()

    def run(self):
        """Run the RVC4 pipeline and workers until shutdown, then stop the model."""
        signal.signal(signal.SIGINT, self._handle_shutdown_signal)
        signal.signal(signal.SIGTERM, self._handle_shutdown_signal)

        device = dai.Device()
        if device.getPlatform() != dai.Platform.RVC4:
            device.close()
            raise RuntimeError("This application supports standalone RVC4 only.")

        # RemoteConnection dispatches frontend requests to these callbacks.
        remote = dai.RemoteConnection(httpPort=8082)
        remote.registerService("Qwen Snapshot", self.snapshot)
        remote.registerService("Qwen Submit", self.submit)
        remote.registerService("Qwen State", self.state)

        try:
            with dai.Pipeline(device) as pipeline:
                # Share the camera output between the live stream and frame capture.
                camera = pipeline.create(dai.node.Camera).build(
                    dai.CameraBoardSocket.CAM_A
                )
                video = camera.requestOutput(
                    (1920, 1080), type=dai.ImgFrame.Type.NV12, fps=20
                )
                encoder = pipeline.create(dai.node.VideoEncoder).build(
                    video,
                    frameRate=20,
                    profile=dai.VideoEncoderProperties.Profile.H264_MAIN,
                )
                remote.addTopic("Video", encoder.out)
                queue = video.createOutputQueue(maxSize=1, blocking=False)

                pipeline.start()
                logger.info("Pipeline started.")
                remote.registerPipeline(pipeline)

                # Capture frames continuously while the model loads independently.
                threading.Thread(
                    target=self.capture, args=(queue,), daemon=True
                ).start()
                threading.Thread(target=self.runtime.start, daemon=True).start()

                # The main thread owns pipeline lifetime and shutdown.
                while pipeline.isRunning():
                    if self.stop.is_set():
                        pipeline.stop()
                        break
                    key = remote.waitKey(1)
                    pipeline.processTasks()
                    if key == ord("q"):
                        logger.info("Got 'q' key. Exiting...")
                        break
                self.stop.set()

        finally:
            self.stop.set()
            self.runtime.close()


if __name__ == "__main__":
    VlmApp().run()
