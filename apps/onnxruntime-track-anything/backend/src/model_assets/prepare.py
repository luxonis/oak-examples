import argparse
import hashlib
import json
from pathlib import Path
import shutil
import threading
import time
import urllib.request
import zipfile

import onnx
from onnx import TensorProto, helper, numpy_helper

from .memory_graph import memory_graph

RELEASE = "v0.63.0"
MODEL_DIRECTORY = Path("/opt/track-anything-models") / RELEASE
MAX_POINTS = 8
ASSETS = {
    "track_anything": "f0ac63783c61aba3453ba7001b2d0f1e967d332cb21265ff36fc6c6a17184d39",
    "mobilesam": "f0fd030d7bc38c12e0e130392dfad7e68eda573b585aae8b7b48e6630d10cc7d",
}


def digest(path):
    """Return a file's SHA-256 digest without loading it all into memory."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def decoder_variant(directory, count):
    """Change only known prompt-length constants in this pinned export.

    Return all four masks; select the appropriate candidate in application code.
    No padding prompts: each count has an exact static graph and cached QNN context.
    External learned tensors continue to reference the verified decoder.data file.

    Args:
        directory: Path to the verified MobileSAM export directory.
        count: Number of prompts in this static decoder variant (1–8).

    Returns:
        Path to the generated ONNX decoder.

    Raises:
        ValueError: The pinned graph no longer matches the expected structure.
    """
    target = directory / f"decoder_points_{count}_v1.onnx"
    model = onnx.load(directory / "decoder.onnx", load_external_data=False)

    for value in model.graph.input:
        if value.name in ("point_coords", "point_labels"):
            value.type.tensor_type.shape.dim[1].dim_value = count

    # Patch the prompt-dependent reshapes as well as the public input shapes.
    expected = {"val_10": [1, 1, 256], "val_455": [1, 32, 6], "val_471": [1, 16, 6]}
    changed = set()
    for tensor in model.graph.initializer:
        if tensor.name in expected:
            a = numpy_helper.to_array(tensor).copy()
            if a.tolist() != expected[tensor.name]:
                raise ValueError("Unexpected MobileSAM graph. Revalidate the exporter.")
            a[1 if tensor.name == "val_10" else 2] = (
                count if tensor.name == "val_10" else count + 5
            )
            tensor.CopyFrom(numpy_helper.from_array(a, tensor.name))
            changed.add(tensor.name)

    if changed != set(expected) or model.graph.node[-8].name != "node_add_29":
        raise ValueError("Unexpected MobileSAM decoder selection graph.")

    # Expose all mask candidates; runtime.select applies SAM's selection rule.
    del model.graph.node[-8:]
    del model.graph.output[:]
    model.graph.output.extend(
        [
            helper.make_tensor_value_info(
                "view_5", TensorProto.FLOAT, [1, 4, 256, 256]
            ),
            helper.make_tensor_value_info("squeeze_201", TensorProto.FLOAT, [1, 4]),
        ]
    )
    del model.graph.value_info[:]

    used = {name for node in model.graph.node for name in node.input}
    kept = [t for t in model.graph.initializer if t.name in used]
    del model.graph.initializer[:]
    model.graph.initializer.extend(kept)

    # Deterministic bytes keep compiled-context model identity stable across starts.
    payload = model.SerializeToString()
    if not target.exists() or target.read_bytes() != payload:
        partial = target.with_suffix(".partial")
        partial.write_bytes(payload)
        partial.replace(target)
    return target


def download_models(directory, progress, stop):
    """Download verified assets and generate static graphs during the image build.

    Args:
        directory: Destination model release directory inside the app image.
        progress: Callback accepting download and verification status messages.
        stop: Threading event used to interrupt downloads and retry waits.

    Returns:
        Path to the verified model release directory, including generated graphs.

    Raises:
        InterruptedError: Shutdown is requested during model preparation.
        ValueError: Download verification fails after retries, or the graph
            structure differs from the pinned export.
    """
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(Path(__file__).with_name("manifest.json").read_text())

    for name, checksum in ASSETS.items():
        folder = root / f"{name}-onnx-float"
        progress(f"Verifying {name} model cache…")
        valid = all(
            (folder / f).is_file() and digest(folder / f) == h
            for f, h in manifest[name].items()
        )

        if not valid:
            archive = root / f"{name}.zip.partial"
            url = f"https://qaihub-public-assets.s3.us-west-2.amazonaws.com/qai-hub-models/models/{name}/releases/{RELEASE}/{name}-onnx-float.zip"
            for attempt in range(3):
                try:
                    with (
                        urllib.request.urlopen(url, timeout=60) as response,
                        archive.open("wb") as f,
                    ):
                        total = int(response.headers.get("Content-Length", 0))
                        downloaded = 0
                        last_report = 0
                        while chunk := response.read(1024 * 1024):
                            if stop.is_set():
                                raise InterruptedError("Application stopping")
                            f.write(chunk)
                            downloaded += len(chunk)

                            if time.monotonic() - last_report > 1:
                                progress(
                                    f"Downloading {name}: {downloaded // 1048576} / {total // 1048576} MB"
                                )
                                last_report = time.monotonic()

                    if digest(archive) != checksum:
                        raise ValueError(f"Checksum mismatch for {name}")

                    # Verify in staging before replacing the current model cache.
                    staging = root / f"{name}.extracting"
                    shutil.rmtree(staging, ignore_errors=True)
                    staging.mkdir()
                    with zipfile.ZipFile(archive) as z:
                        for member in z.infolist():
                            dest = (staging / member.filename).resolve()
                            if not dest.is_relative_to(staging.resolve()):
                                raise ValueError("Unsafe archive member")
                        z.extractall(staging)

                    extracted = staging / folder.name
                    if not all(
                        digest(extracted / f) == h for f, h in manifest[name].items()
                    ):
                        raise ValueError(
                            f"Extracted model verification failed for {name}"
                        )

                    shutil.rmtree(folder, ignore_errors=True)
                    extracted.replace(folder)
                    staging.rmdir()
                    archive.unlink()
                    break
                except Exception:
                    archive.unlink(missing_ok=True)
                    if stop.is_set() or attempt == 2:
                        raise
                    progress(f"Retrying {name} download…")
                    stop.wait(2 ** (attempt + 1))

        if stop.is_set():
            raise InterruptedError("Application stopping")

    # Exact static dimensions allow QNN to compile and cache each graph variant.
    for count in range(1, MAX_POINTS + 1):
        decoder_variant(root / "mobilesam-onnx-float", count)

    for count in range(1, 6):
        memory_graph(
            root / "track_anything-onnx-float" / f"memory_read_{count}_v1.onnx", count
        )

    return root


def ensure_models(progress, stop):
    """Verify the bundled models without downloading or writing runtime files.

    Args:
        progress: Callback accepting verification status messages.
        stop: Threading event indicating application shutdown.

    Returns:
        Path to the model release directory baked into the container image.

    Raises:
        InterruptedError: Shutdown is requested during verification.
        ValueError: Bundled model files are missing or fail verification.
    """
    manifest = json.loads(Path(__file__).with_name("manifest.json").read_text())
    for name, files in manifest.items():
        progress(f"Verifying bundled {name} models…")
        for filename, checksum in files.items():
            if stop.is_set():
                raise InterruptedError("Application stopping")
            path = MODEL_DIRECTORY / f"{name}-onnx-float" / filename
            if not path.is_file() or digest(path) != checksum:
                raise ValueError(
                    f"Bundled model is missing or invalid: {path}. Rebuild the app image."
                )

    variants = [
        MODEL_DIRECTORY / "mobilesam-onnx-float" / f"decoder_points_{count}_v1.onnx"
        for count in range(1, MAX_POINTS + 1)
    ] + [
        MODEL_DIRECTORY / "track_anything-onnx-float" / f"memory_read_{count}_v1.onnx"
        for count in range(1, 6)
    ]
    for path in variants:
        if not path.is_file():
            raise ValueError(
                f"Bundled graph is missing: {path}. Rebuild the app image."
            )

    return MODEL_DIRECTORY


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Bake verified ONNX models into the app image."
    )
    parser.add_argument("--directory", type=Path, default=MODEL_DIRECTORY)
    download_models(parser.parse_args().directory, print, threading.Event())
