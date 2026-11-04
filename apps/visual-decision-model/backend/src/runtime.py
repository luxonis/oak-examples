import logging as log
import subprocess
import threading
import time
from pathlib import Path

import requests

from models import FILES
from decision import native_question, parse_answers


logger = log.getLogger(__name__)


class Runtime:
    """Manage the local llama-server process and its HTTP connection.

    Start the server and score decisions through its loopback /v1/systemone API.
    """

    def __init__(self, stop):
        self.stop = stop
        self.process = None

        # Loading, log reading, and frontend polling share model status.
        self.lock = threading.Lock()
        self.status = "Starting"
        self.ready = False
        self.error = None
        self.placement = []

        self.url = "http://127.0.0.1:8081"

    def update(self, message):
        with self.lock:
            self.status = message

        logger.info("[model] %s", message)

    name = "d3-lite Q8_0"

    def command(self):
        model, projector = [Path("/opt/d3-models") / name for name in FILES]
        if not model.is_file() or not projector.is_file():
            raise RuntimeError("Model assets missing; rebuild the app image.")
        # d3 evaluates the entire decision input in one physical batch.
        return [
            "llama-server",
            "--model",
            str(model),
            "--mmproj",
            str(projector),
            "--device",
            "HTP0",
            "--mmproj-device",
            "HTP0",
            "-ngl",
            "99",
            "--host",
            "127.0.0.1",
            "--port",
            "8081",
            "--parallel",
            "1",
            "--ctx-size",
            "4096",
            "--batch-size",
            "4096",
            "--ubatch-size",
            "4096",
            "--threads",
            "4",
            "--threads-batch",
            "4",
            "--no-warmup",
            "--verbosity",
            "4",
        ]

    def start(self):
        """Launch the server and record startup errors for the frontend."""
        try:
            if self.stop.is_set():
                return
            self.update(f"Loading {self.name} on Hexagon")
            command = self.command()

            self.process = subprocess.Popen(
                command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
            )
            # Drain stdout continuously so the server cannot block on a full pipe.
            threading.Thread(target=self.read_logs, daemon=True).start()

            # Loading is complete only when the HTTP health check succeeds.
            deadline = time.monotonic() + 180
            while not self.stop.is_set() and time.monotonic() < deadline:
                if self.process.poll() is not None:
                    raise RuntimeError(
                        f"llama-server exited with code {self.process.returncode}; see app logs."
                    )

                try:
                    response = requests.get(self.url + "/health", timeout=2)
                    if response.ok:
                        with self.lock:
                            self.ready = True
                        self.update("Ready")
                        return
                except requests.RequestException:
                    pass
                self.stop.wait(0.5)

            if not self.stop.is_set():
                raise RuntimeError("Timed out waiting for llama-server.")

        except Exception as exc:
            with self.lock:
                self.error = str(exc)
            self.update("Model unavailable")
            logger.error("[model] %s", exc)

    def read_logs(self):
        for line in self.process.stdout:
            if any(
                marker in line for marker in ("using device", "offloaded", "CLIP using")
            ):
                with self.lock:
                    self.placement.append(line.strip())
                    self.placement = self.placement[-12:]
            if any(
                marker in line.lower()
                for marker in (
                    "error",
                    "warning",
                    "model loaded",
                    "using device",
                    "offloaded",
                )
            ):
                logger.info("[%s] %s", self.name, line.rstrip())

    def state(self):
        with self.lock:
            alive = self.process is not None and self.process.poll() is None
            return {
                "ready": self.ready and alive,
                "status": self.status if not self.ready or alive else "Model stopped",
                "error": self.error,
                "name": self.name,
                "backend": "Hexagon HTP0",
                "placement": list(self.placement),
            }

    def decide(self, context, questions, images):
        """Submit exactly the selected question and measure the complete model request."""
        payload = {
            "state": context or None,
            "images": images,
            "questions": {
                f"q{i + 1}": native_question(question)
                for i, question in enumerate(questions)
            },
        }
        started = time.monotonic()
        response = requests.post(
            self.url + "/v1/systemone", json=payload, timeout=(10, 180)
        )
        if not response.ok:
            raise RuntimeError(
                f"d3 inference failed ({response.status_code}): {response.text[:500]}"
            )
        answers = parse_answers(response.json(), questions)
        return {
            "answers": answers,
            "model_ms": round((time.monotonic() - started) * 1000, 1),
        }

    def close(self):
        """Terminate llama-server, forcing exit if it exceeds the shutdown timeout."""
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                # Force shutdown only if the server did not exit gracefully.
                self.process.kill()
                self.process.wait()
