import json
import logging as log
import subprocess
import threading
import time
from pathlib import Path

import requests

from constants import load_config, validate_max_tokens, validate_temperature
from models import FILES


logger = log.getLogger(__name__)


class Runtime:
    """Manage the local llama-server process and its HTTP connection.

    Start the server, monitor its readiness, and stream inference responses
    through its OpenAI-compatible API at http://127.0.0.1:8081.
    """

    def __init__(self, stop, config=None):
        self.config = config if config is not None else load_config()
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

    def start(self):
        """Launch llama-server and await readiness, recording startup errors in state."""
        try:
            model, projector = [Path("/opt/qwen-models") / name for name in FILES]
            if not model.is_file() or not projector.is_file():
                raise RuntimeError(
                    "Model assets are missing; rebuild the app container."
                )
            if self.stop.is_set():
                return

            self.update("Loading Qwen3.5-0.8B on Hexagon")
            settings = self.config["runtime"]
            command = [
                # Model files and Hexagon placement.
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
                # Local endpoint and inference capacity.
                "--host",
                "127.0.0.1",
                "--port",
                "8081",
                "--ctx-size",
                str(settings["context_size"]),
                "--parallel",
                "1",
                "--threads",
                str(settings["threads"]),
                "--threads-batch",
                str(settings["threads"]),
                "--batch-size",
                str(settings["batch_size"]),
                "--ubatch-size",
                str(settings["ubatch_size"]),
                # Runtime and vision preprocessing options from config.yaml.
                "--flash-attn",
                settings["flash_attention"],
                "--fit",
                "on" if settings["fit"] else "off",
                "--context-shift"
                if settings["context_shift"]
                else "--no-context-shift",
                "--cache-ram",
                str(settings["cache_ram_mb"]),
                "--image-min-tokens",
                str(settings["image_min_tokens"]),
                "--image-max-tokens",
                str(settings["image_max_tokens"]),
                "--jinja",
                "--no-warmup",
                "--verbosity",
                "4",
            ]

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
            logger.info("[llama] %s", line.rstrip())

            if any(
                marker in line for marker in ("using device", "offloaded", "CLIP using")
            ):
                with self.lock:
                    self.placement.append(line.strip())
                    self.placement = self.placement[-12:]

    def state(self):
        with self.lock:
            alive = self.process is not None and self.process.poll() is None
            return {
                "ready": self.ready and alive,
                "status": self.status if not self.ready or alive else "Model stopped",
                "error": self.error,
                "name": "Qwen3.5-0.8B Q4_0",
                "backend": "Hexagon HTP0",
                "placement": list(self.placement),
            }

    def generate(self, prompt, image, update, max_tokens=None, temperature=None):
        """Stream one image/prompt request and measure first/last answer latency.

        Args:
            prompt: User prompt text.
            image: JPEG data URL for the prepared full frame or crop.
            update: Callback receiving accumulated text, first-token milliseconds,
                and latest-token milliseconds for each nonempty text event.
            max_tokens: Output-token limit (1-256), or None for the config default.
            temperature: Sampling temperature (0-1), or None for the config default.

        Returns:
            A dictionary containing text, ttft_ms, total_ms, and finish_reason.
            Timings start at the HTTP request; total_ms ends at the last text event.

        Raises:
            ValueError: A generation setting is invalid or an event is invalid JSON.
            requests.RequestException: The HTTP request fails or times out.
            RuntimeError: Shutdown is requested, the server reports an error, or
                the response has no answer text or completion reason.
        """
        defaults = self.config["generation"]
        payload = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": image}},
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
            "stream": True,
            "stream_options": {"include_usage": True},
            "max_tokens": validate_max_tokens(
                defaults["max_tokens"] if max_tokens is None else max_tokens
            ),
            "temperature": validate_temperature(
                defaults["temperature"] if temperature is None else temperature
            ),
            "chat_template_kwargs": {"enable_thinking": False},
        }

        # Exclude app-side cropping and JPEG encoding from model latency.
        started = time.monotonic()
        first = last = None
        text = ""
        finish_reason = None

        # chunk_size=1 prevents requests buffering short token events for display/timing.
        with requests.post(
            self.url + "/v1/chat/completions",
            json=payload,
            stream=True,
            timeout=(10, 180),
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines(chunk_size=1):
                if self.stop.is_set():
                    raise RuntimeError("Application is stopping.")
                if not line.startswith(b"data: "):
                    continue

                data = line[6:]
                if data == b"[DONE]":
                    break
                event = json.loads(data)
                if "error" in event:
                    raise RuntimeError(str(event["error"]))

                # Empty role and completion events do not count as answer tokens.
                for choice in event.get("choices", []):
                    token = choice.get("delta", {}).get("content")
                    if token:
                        last = time.monotonic()
                        first = first if first is not None else last
                        text += token
                        update(text, (first - started) * 1000, (last - started) * 1000)
                    finish_reason = choice.get("finish_reason") or finish_reason

        if first is None:
            raise RuntimeError("The model returned no answer text.")
        if finish_reason is None:
            raise RuntimeError("The model stream ended before completion.")

        return {
            "text": text,
            "ttft_ms": round((first - started) * 1000, 1),
            "total_ms": round((last - started) * 1000, 1),
            "finish_reason": finish_reason,
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
