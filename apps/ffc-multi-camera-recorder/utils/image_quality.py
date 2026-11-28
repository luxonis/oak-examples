"""Image processing for monochrome cameras that cannot use the RVC4 ISP."""

import math

import depthai as dai
import numpy as np


RAW10_WHITE = 1023
LUMA_BLACK = 16
LUMA_WHITE = 235
MAX_EXPOSURE_US = 33000
MAX_DIGITAL_GAIN = 8.0
EXPOSURE_INTERVAL = 0.5


def unpack_raw10(raw):
    """Unpack all ten MIPI bits, excluding any padding at the end of a row."""
    width, height, stride = raw.getWidth(), raw.getHeight(), raw.getStride()
    if raw.getType() != dai.ImgFrame.Type.RAW10:
        raise ValueError(f"Expected packed RAW10, got {raw.getType()}")
    if width <= 0 or height <= 0 or width % 4 or height % 2:
        raise ValueError(f"Unsupported RAW10 dimensions: {width}x{height}")
    row_bytes = width * 5 // 4
    if stride < row_bytes:
        raise ValueError("RAW10 stride is shorter than a packed row")
    data = raw.getData()
    if len(data) < stride * height:
        raise ValueError("Short RAW10 camera frame")
    packed = data[: stride * height].reshape(height, stride)
    groups = packed[:, :row_bytes].reshape(height, width // 4, 5).astype(np.uint16)
    low_bits = (groups[:, :, 4, None] >> np.arange(0, 8, 2, dtype=np.uint16)) & 3
    return ((groups[:, :, :4] << 2) | low_bits).reshape(height, width)


class RawImageProcessor:
    """Correct raw tones and calibrate exposure once at recording startup.

    Exposure is metered after tone mapping to the same luma target as the ISP
    cameras. Prefer real exposure to digital gain. Raw-only RVC4 paths can
    ignore requested ISO, so bounded digital gain handles remaining low light.
    After the settling period, exposure and digital gain stay fixed until restart.
    """

    def __init__(
        self,
        fps,
        exposure_us=10000,
        iso=400,
        *,
        auto_exposure=True,
        gamma=2.2,
        black_level=64,
        settle_seconds=10.0,
    ):
        self.max_exposure_us = max(1, min(MAX_EXPOSURE_US, int(1_000_000 / fps)))
        self.exposure_us = min(exposure_us, self.max_exposure_us)
        self.iso = iso
        self.auto_exposure = auto_exposure
        self.settle_seconds = settle_seconds
        self.first_timestamp = None
        self.locked = not auto_exposure
        self.gamma = gamma
        self.black_level = black_level
        self.digital_gain = 1.0
        self.luma = 0.0
        self.last_adjustment = None
        self._update_lut()

    def _update_lut(self):
        linear = np.maximum(np.arange(1024, dtype=np.float32) - self.black_level, 0)
        linear *= self.digital_gain / (RAW10_WHITE - self.black_level)
        encoded = np.clip(linear, 0, 1) ** (1 / self.gamma)
        self.lut = np.rint(LUMA_BLACK + (LUMA_WHITE - LUMA_BLACK) * encoded).astype(
            np.uint8
        )

    def _adjust_exposure(self, raw, gray, target_luma):
        timestamp = raw.getTimestampDevice().total_seconds()
        if self.first_timestamp is None:
            self.first_timestamp = timestamp
        if timestamp - self.first_timestamp >= self.settle_seconds:
            self.locked = True
        if (
            self.last_adjustment is not None
            and timestamp - self.last_adjustment < EXPOSURE_INTERVAL
        ):
            return None
        self.last_adjustment = timestamp
        # Sample the entire field of view, including corners, without scanning
        # every pixel for statistics. A deadband avoids chasing sensor noise.
        sample = gray[::8, ::8]
        self.luma = float(self.lut[sample].mean())
        if self.locked:
            return None
        target = float(np.clip(target_luma, 48, 192))
        if abs(target - self.luma) < 3:
            return None
        ratio = (target - LUMA_BLACK) / max(self.luma - LUMA_BLACK, 1)
        multiplier = float(np.clip(ratio ** (self.gamma * 0.5), 0.7, 1.4))
        # If a substantial area is already saturated, avoid increasing exposure
        # merely to brighten its dark surroundings. Tiny highlights may clip.
        if np.mean(sample >= RAW10_WHITE - 4) > 0.02:
            multiplier = min(multiplier, 0.9)
        actual_us = round(raw.getExposureTime().total_seconds() * 1_000_000)
        actual_us = actual_us if actual_us > 0 else self.exposure_us
        total_exposure = actual_us * self.digital_gain * multiplier
        exposure_us = round(np.clip(total_exposure, 1, self.max_exposure_us))
        gain = float(np.clip(total_exposure / exposure_us, 1, MAX_DIGITAL_GAIN))
        if not math.isclose(gain, self.digital_gain, rel_tol=0.01):
            self.digital_gain = gain
            self._update_lut()
        if abs(exposure_us - self.exposure_us) < max(1, self.exposure_us * 0.01):
            return None
        self.exposure_us = exposure_us
        control = dai.CameraControl()
        control.setManualExposure(exposure_us, self.iso)
        return control

    def convert(self, raw, target_luma=96):
        """Return an encoder-ready frame and an optional sensor control message."""
        gray = unpack_raw10(raw)
        height, width = gray.shape
        nv12 = np.empty((height * 3 // 2, width), dtype=np.uint8)
        nv12[:height] = self.lut[gray]
        nv12[height:] = 128
        # Meter only after this frame is rendered: any changed gain belongs to
        # the next frame, just as sensor exposure changes take effect later.
        control = self._adjust_exposure(raw, gray, target_luma)
        frame = dai.ImgFrame()
        frame.setData(nv12)
        frame.setWidth(width)
        frame.setHeight(height)
        frame.setType(dai.ImgFrame.Type.NV12)
        frame.setSequenceNum(raw.getSequenceNum())
        frame.setTimestamp(raw.getTimestamp())
        frame.setTimestampDevice(raw.getTimestampDevice())
        return frame, control


class BrightnessReference:
    """Smooth the median brightness of recent ISP camera previews."""

    def __init__(self):
        self.samples = {}
        self.target = 96.0

    def observe(self, socket, frame, now):
        height, width, stride = frame.getHeight(), frame.getWidth(), frame.getStride()
        luma = frame.getData()[: height * stride].reshape(height, stride)[:, :width]
        self.samples[socket] = (now, float(luma.mean()))

    def update(self, now):
        recent = [
            mean for timestamp, mean in self.samples.values() if now - timestamp < 2
        ]
        if recent:
            desired = float(np.clip(np.median(recent), 48, 192))
            self.target += 0.2 * (desired - self.target)
        return self.target
