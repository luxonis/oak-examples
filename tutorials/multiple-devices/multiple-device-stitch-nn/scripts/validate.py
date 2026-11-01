"""Run the normal example and capture bounded live evidence through the Visualizer."""

import signal
import socket
import subprocess
import sys
import time
from pathlib import Path


def main():
    example = Path(__file__).resolve().parents[1]
    process = subprocess.Popen(
        [sys.executable, str(example / "main.py"), *sys.argv[1:]]
    )
    try:
        deadline = time.monotonic() + 60
        while True:
            if process.poll() is not None:
                raise RuntimeError("Example exited before the Visualizer was ready")
            try:
                with socket.create_connection(("127.0.0.1", 8765), timeout=1):
                    break
            except OSError:
                if time.monotonic() >= deadline:
                    raise TimeoutError("Visualizer did not start within 60 seconds")
                time.sleep(0.25)
        subprocess.run(
            [
                "oakctl",
                "inspect",
                "frames",
                "Stitched",
                "--count",
                "2",
                "--out",
                "evidence/panorama",
                "--timeout",
                "60s",
            ],
            check=True,
            timeout=65,
        )
        subprocess.run(
            [
                "oakctl",
                "inspect",
                "frames",
                "Inference",
                "--count",
                "1",
                "--out",
                "evidence/inference",
                "--timeout",
                "20s",
            ],
            check=True,
            timeout=25,
        )
        subprocess.run(
            [
                "oakctl",
                "inspect",
                "dump",
                "PanoramaDetections",
                "--count",
                "2",
                "--timeout",
                "20s",
            ],
            check=True,
            timeout=25,
        )
    finally:
        if process.poll() is None:
            process.send_signal(signal.SIGINT)
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == "__main__":
    main()
