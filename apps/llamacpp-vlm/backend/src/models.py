"""Bake pinned Apache-2.0 Qwen assets into the app container at build time."""

import hashlib
import argparse
from pathlib import Path

import requests

REPOSITORY = "unsloth/Qwen3.5-0.8B-GGUF"
REVISION = "6ab461498e2023f6e3c1baea90a8f0fe38ab64d0"
FILES = {
    "Qwen3.5-0.8B-Q4_0.gguf": "444406ddd926550c724ec18d5120a9d40ded44908a063b0e66e9a7e5464c652c",
    "mmproj-F16.gguf": "56e4c6cfe73b0c82e3e82bc518d7591997e61d81f723fc41a586f4fa69ea2453",
}


def sha256(path):
    """Return a file's SHA-256 hex digest without loading it all into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def download_models(directory, update=print):
    """Install the pinned model files during the app container build.

    Args:
        directory: Destination directory inside the app image.
        update: Callback receiving progress messages; defaults to print.

    Returns:
        Paths to the verified model and projector, in FILES order.

    Raises:
        requests.RequestException: A download fails or times out.
        RuntimeError: A downloaded file does not match its SHA-256 checksum.
        OSError: A local file cannot be read, written, or replaced.
    """
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)

    for name, checksum in FILES.items():
        destination = directory / name
        update(f"Checking {name}")
        # Reuse a file only after verifying its complete contents.
        if destination.exists() and sha256(destination) == checksum:
            continue

        update(f"Downloading {name} (app build)")
        temporary = destination.with_suffix(".part")
        try:
            url = f"https://huggingface.co/{REPOSITORY}/resolve/{REVISION}/{name}"
            with requests.get(url, stream=True, timeout=(20, 120)) as response:
                response.raise_for_status()
                with temporary.open("wb") as output:
                    for chunk in response.iter_content(1024 * 1024):
                        output.write(chunk)

            # Publish the finished file only after checksum verification.
            if sha256(temporary) != checksum:
                raise RuntimeError(f"Checksum mismatch for {name}")
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)

    return [directory / name for name in FILES]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", default="/opt/qwen-models")
    download_models(parser.parse_args().directory)
