"""Bake pinned Apache-2.0 d3-lite assets into the app container at build time."""

import hashlib
import argparse
import logging as log
from pathlib import Path

import requests

logger = log.getLogger(__name__)

REPOSITORY = "ggml-org/vllm-d3-lite-GGUF"
REVISION = "a1f9fa124e8d60ac02d1a2884b1dec5a3ec2fd21"
FILES = {
    "vllm-d3-lite-Q8_0.gguf": "7a5175f51ad59928e358bdacacece2fd222927fa2975c859b2c76b68951099b1",
    "mmproj-vllm-d3-lite-Q8_0.gguf": "40d3a061297657928dcb6ddc055f175bde582c3696483c1b70fc08c35b087255",
}


def sha256(path):
    """Return a file's SHA-256 hex digest without loading it all into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def download_models(
    directory, update=logger.info, repository=REPOSITORY, revision=REVISION, files=None
):
    """Install the pinned model files during the app container build.

    Args:
        directory: Destination directory inside the app image.
        update: Callback receiving progress messages; defaults to logger.info.
        repository: Hugging Face repository containing the assets.
        revision: Exact immutable source revision.
        files: Filename to SHA-256 mapping; defaults to the d3-lite pair.

    Returns:
        Paths to the verified model and projector, in FILES order.

    Raises:
        requests.RequestException: A download fails or times out.
        RuntimeError: A downloaded file does not match its SHA-256 checksum.
        OSError: A local file cannot be read, written, or replaced.
    """
    files = FILES if files is None else files
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)

    for name, checksum in files.items():
        destination = directory / name
        update(f"Checking {name}")
        # Reuse a file only after verifying its complete contents.
        if destination.exists() and sha256(destination) == checksum:
            continue

        update(f"Downloading {name} (app build)")
        temporary = destination.with_suffix(".part")
        try:
            url = f"https://huggingface.co/{repository}/resolve/{revision}/{name}"
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

    return [directory / name for name in files]


if __name__ == "__main__":
    log.basicConfig(level=log.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", default="/opt/d3-models")
    directory = parser.parse_args().directory
    download_models(directory)
