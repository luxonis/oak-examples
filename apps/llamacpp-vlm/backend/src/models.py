"""Bake pinned Apache-2.0 Qwen assets into the app container at build time."""

import hashlib
import argparse
import logging as log
from pathlib import Path

import requests

logger = log.getLogger(__name__)

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


def download(url, temporary, update=logger.info, attempts=5):
    """Download url into temporary, resuming with HTTP Range after a broken transfer.

    Args:
        url: Source URL.
        temporary: Destination path; an existing partial file is continued.
        update: Callback receiving progress messages.
        attempts: Total number of attempts before giving up.

    Raises:
        requests.RequestException: The last attempt failed or timed out.
    """
    failed_attempts = 0
    while failed_attempts < attempts:
        offset = temporary.stat().st_size if temporary.exists() else 0
        headers = {"Range": f"bytes={offset}-"} if offset else {}
        try:
            with requests.get(
                url, stream=True, timeout=(20, 120), headers=headers
            ) as response:
                if offset and response.status_code == 416:
                    # The partial file is at or beyond the remote file's end.
                    # Discard it and try a full download without spending a retry.
                    temporary.unlink()
                    update("Partial download is not resumable; restarting from zero")
                    continue
                if offset and response.status_code != 206:
                    # Server ignored the range request: start over.
                    offset = 0
                response.raise_for_status()
                with temporary.open("ab" if offset else "wb") as output:
                    for chunk in response.iter_content(1024 * 1024):
                        output.write(chunk)
            return
        except requests.RequestException as error:
            failed_attempts += 1
            if failed_attempts == attempts:
                raise
            update(
                f"Download interrupted ({error}); retrying "
                f"{failed_attempts}/{attempts - 1}"
            )


def download_models(directory, update=logger.info):
    """Install the pinned model files during the app container build.

    Args:
        directory: Destination directory inside the app image.
        update: Callback receiving progress messages; defaults to logger.info.

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

        temporary = destination.with_suffix(".part")
        try:
            # A previous run may have finished the transfer but stopped before
            # publishing the verified file.
            if temporary.exists() and sha256(temporary) == checksum:
                temporary.replace(destination)
                continue

            update(f"Downloading {name} (app build)")
            url = f"https://huggingface.co/{REPOSITORY}/resolve/{REVISION}/{name}"
            download(url, temporary, update)

            # Publish the finished file only after checksum verification.
            if sha256(temporary) != checksum:
                raise RuntimeError(f"Checksum mismatch for {name}")
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)

    return [directory / name for name in FILES]


if __name__ == "__main__":
    log.basicConfig(level=log.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", default="/opt/qwen-models")
    download_models(parser.parse_args().directory)
