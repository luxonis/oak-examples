import base64
import math

import cv2


def prepare_image(frame, region=None, max_edge=448):
    """Crop the original frame, then downscale while preserving aspect ratio.

    Args:
        frame: Nonempty OpenCV BGR image from the camera or saved snapshot.
        region: Optional dictionary of normalized x, y, width, and height.
            Coordinates refer to the original frame, with the origin at top-left.
        max_edge: Positive maximum output edge length in pixels.

    Returns:
        A BGR image with neither edge exceeding max_edge. Small crops are
        not enlarged, and no padding is added.

    Raises:
        ValueError: The region is malformed, outside the frame, or maps to
            a crop smaller than 16 pixels in either dimension.
    """
    height, width = frame.shape[:2]

    if region is not None:
        if not isinstance(region, dict):
            raise ValueError("Region must contain normalized x, y, width and height.")

        values = [region.get(key) for key in ("x", "y", "width", "height")]
        if any(
            isinstance(v, bool)
            or not isinstance(v, (float, int))
            or not math.isfinite(v)
            for v in values
        ):
            raise ValueError("Region coordinates must be finite numbers.")

        x, y, w, h = values
        if x < 0 or y < 0 or w <= 0 or h <= 0 or x + w > 1.000001 or y + h > 1.000001:
            raise ValueError("Region must stay inside the image.")

        # Map the frontend rectangle onto the original full-resolution snapshot.
        left, top = int(x * width), int(y * height)
        right, bottom = (
            min(width, math.ceil((x + w) * width)),
            min(height, math.ceil((y + h) * height)),
        )
        if right - left < 16 or bottom - top < 16:
            raise ValueError("Select a region at least 16 pixels wide and high.")
        frame = frame[top:bottom, left:right]

    # Downscale after cropping; never enlarge small regions or change their aspect ratio.
    height, width = frame.shape[:2]
    scale = min(1.0, max_edge / max(width, height))
    size = (max(1, round(width * scale)), max(1, round(height * scale)))
    return cv2.resize(frame, size, interpolation=cv2.INTER_AREA)


def jpeg_data_url(frame, quality=85):
    """Encode an OpenCV BGR image as a JPEG data URL for the model or frontend."""
    success, data = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not success:
        raise RuntimeError("Could not encode the camera image.")

    return "data:image/jpeg;base64," + base64.b64encode(data).decode("ascii")
