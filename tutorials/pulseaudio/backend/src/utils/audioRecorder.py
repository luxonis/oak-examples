import logging
import signal
import subprocess
import time
from contextlib import suppress
from pathlib import Path

logger = logging.getLogger(__name__)


class AudioRecorder:
    def __init__(
        self,
        recordings_dir: str = "/data/recordings",
        rate: int = 48000,
        channels: int = 2,
        fmt: str = "s32le",
        device: str | None = None,
    ):
        self.recordings_dir = Path(recordings_dir)
        self.recordings_dir.mkdir(parents=True, exist_ok=True)
        self.rate, self.channels, self.format, self.device = rate, channels, fmt, device
        self._process: subprocess.Popen | None = None
        self._output_path: Path | None = None

    @property
    def is_recording(self) -> bool:
        return self._process is not None

    @property
    def output_path(self) -> Path | None:
        return self._output_path

    def start(self) -> Path | None:
        if self._process:
            logger.warning("Recording already in progress")
            return self._output_path

        self._output_path = self.recordings_dir / f"recording_{int(time.time())}.wav"

        cmd = [
            "parec",
            f"--rate={self.rate}",
            f"--format={self.format}",
            f"--channels={self.channels}",
            "--file-format=wav",
            str(self._output_path),
        ]
        if self.device:
            cmd += ["--device", self.device]

        logger.info("Starting audio recording: %s", self._output_path)
        logger.debug("Running command: %s", " ".join(cmd))

        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
            )
            time.sleep(0.2)
            if self._process.poll() is not None:
                err = ""
                with suppress(Exception):
                    if self._process.stderr:
                        err = self._process.stderr.read().strip()
                logger.error(
                    "parec exited immediately (rc=%s). Recording did not start. stderr: %s",
                    self._process.returncode,
                    err or "<no stderr>",
                )
                self._process = None
                return None
            return self._output_path
        except Exception:
            logger.exception("Failed to start recording")
            self._process = None
            return None

    def stop(self) -> Path | None:
        if not self._process:
            logger.warning("Stop called but no recording in progress")
            return None

        logger.info("Stopping audio recording...")
        proc, self._process = self._process, None

        def _wait(timeout: float) -> bool:
            with suppress(subprocess.TimeoutExpired):
                proc.wait(timeout=timeout)
                return True
            return False

        with suppress(Exception):
            proc.send_signal(signal.SIGINT)
        if not _wait(5):
            logger.warning("parec did not stop within timeout; terminating...")
            with suppress(Exception):
                proc.terminate()
            if not _wait(2):
                logger.warning("parec still running; killing...")
                with suppress(Exception):
                    proc.kill()
                _wait(2)

        with suppress(Exception):
            if proc.stderr:
                err = proc.stderr.read().strip()
                if err:
                    logger.debug("parec stderr: %s", err)

        logger.info("Recording saved to: %s", self._output_path)
        return self._output_path
