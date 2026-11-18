"""Bound image inputs before decoding and preserve their aspect ratio."""

import base64
import binascii
import io
import cv2
from PIL import Image, UnidentifiedImageError
from decision import validate_decision

MAX_REFERENCES = 7
MAX_DATA_URL = 700_000
MAX_EDGE = 448
Image.MAX_IMAGE_PIXELS = 16_000_000


def validate_request(message):
    """Validate cheap request properties before reserving the inference worker."""
    if not isinstance(message, dict):
        raise ValueError("Expected a prompt and optional reference images.")
    context = message.get("context", "")
    if not isinstance(context, str) or len(context) > 2000:
        raise ValueError("Scene context must be text of at most 2000 characters.")
    decision = validate_decision(message.get("decision"))
    references = message.get("references", [])
    if not isinstance(references, list) or len(references) > MAX_REFERENCES:
        raise ValueError("Use at most seven reference images.")
    for value in references:
        if (
            not isinstance(value, str)
            or len(value) > MAX_DATA_URL
            or not value.startswith(
                ("data:image/jpeg;base64,", "data:image/png;base64,")
            )
        ):
            raise ValueError(
                "Reference images must be JPEG or PNG data URLs under 700 KB each."
            )
    return context.strip(), decision, list(references)


def jpeg_data_url(frame, max_edge=MAX_EDGE):
    """Encode a BGR frame, optionally limiting its longest edge.

    Args:
        frame: Source or crop in BGR format.
        max_edge: Maximum output edge; defaults to the d3-lite image input limit.
    """
    height, width = frame.shape[:2]
    ratio = min(1, max_edge / max(height, width))
    if ratio < 1:
        frame = cv2.resize(
            frame,
            (max(1, round(width * ratio)), max(1, round(height * ratio))),
            interpolation=cv2.INTER_AREA,
        )
    ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not ok:
        raise ValueError("Could not encode the camera frame.")
    return "data:image/jpeg;base64," + base64.b64encode(encoded).decode("ascii")


def prepare_reference(value):
    """Validate actual dimensions before decompression, then normalize to RGB JPEG."""
    try:
        data = base64.b64decode(value.split(",", 1)[1], validate=True)
        with Image.open(io.BytesIO(data)) as source:
            if (
                source.format not in ("JPEG", "PNG")
                or min(source.size) < 16
                or max(source.size) > MAX_EDGE
            ):
                raise ValueError(
                    "Reference images must be 16–448 pixels per side; use the upload control to resize them."
                )
            source.load()
            rgb = source.convert("RGB")
            output = io.BytesIO()
            rgb.save(output, format="JPEG", quality=85)
        return "data:image/jpeg;base64," + base64.b64encode(output.getvalue()).decode(
            "ascii"
        )
    except (
        binascii.Error,
        UnidentifiedImageError,
        OSError,
        Image.DecompressionBombError,
    ) as exc:
        raise ValueError("A reference image could not be decoded.") from exc
