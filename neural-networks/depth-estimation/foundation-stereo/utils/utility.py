import cv2
import numpy as np
from typing import Tuple


class TextHelper:
    def __init__(self) -> None:
        self.bg_color = (0, 0, 0)
        self.color = (255, 255, 255)
        self.text_type = cv2.FONT_HERSHEY_SIMPLEX
        self.line_type = cv2.LINE_AA
        self.font_scale = 0.6
        self.thickness = 1

    def putText(self, frame, text, coords):
        cv2.putText(
            frame,
            text,
            coords,
            self.text_type,
            self.font_scale,
            self.bg_color,
            5,
            self.line_type,
        )
        cv2.putText(
            frame,
            text,
            coords,
            self.text_type,
            self.font_scale,
            self.color,
            self.thickness,
            self.line_type,
        )
        return frame

    def putCenteredText(self, frame, text):
        """Draw text centered in the frame."""
        (text_width, text_height), _ = cv2.getTextSize(
            text, self.text_type, self.font_scale, self.thickness
        )
        x = (frame.shape[1] - text_width) // 2
        y = (frame.shape[0] + text_height) // 2
        return self.putText(frame, text, (x, y))

    def rectangle(self, frame, topLeft, bottomRight, size=1.0):
        cv2.rectangle(frame, topLeft, bottomRight, self.bg_color, int(size * 4))
        cv2.rectangle(frame, topLeft, bottomRight, self.color, int(size))
        return frame


def letterbox_resize(
    image: np.ndarray,
    target_size: Tuple[int, int],
    color: Tuple[int, int, int] = (0, 0, 0),
):
    """Resize image with unchanged aspect ratio using padding."""
    target_h, target_w = target_size
    h, w = image.shape[:2]

    # Compute scale and new size
    scale = min(target_w / w, target_h / h)
    new_w, new_h = int(w * scale), int(h * scale)
    resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

    # Ensure 3-channel image
    if resized.ndim == 2:
        resized = cv2.cvtColor(resized, cv2.COLOR_GRAY2BGR)
    elif resized.shape[2] == 1:
        resized = np.repeat(resized, 3, axis=2)

    # Padding
    canvas = np.full((target_h, target_w, 3), color, dtype=resized.dtype)
    x_off = (target_w - new_w) // 2
    y_off = (target_h - new_h) // 2
    canvas[y_off : y_off + new_h, x_off : x_off + new_w] = resized

    return canvas, scale, (x_off, y_off)


def postprocess_disp(disparity: np.ndarray):
    """Normalizes disparity between 0-255 and applies colormap"""
    norm_disp = cv2.normalize(disparity, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    return cv2.applyColorMap(norm_disp, cv2.COLORMAP_JET)
