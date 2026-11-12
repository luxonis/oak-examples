"""Message builders and output polling shared by host-only pipeline harnesses."""

import time
from datetime import timedelta

import depthai as dai
import numpy as np


def frame_metadata(seq: int = 0) -> dict:
    """Keyword arguments for a message's required timestamps and sequence number."""
    return {
        "timestamp": timedelta(seconds=seq),
        "timestamp_device": timedelta(seconds=seq + 10),
        "sequence_num": seq,
    }


def stamp(message, seq: int):
    """Give ``message`` sequence number ``seq`` and timestamps derived from it."""
    message.setSequenceNum(seq)
    message.setTimestamp(timedelta(seconds=seq))
    message.setTimestampDevice(timedelta(seconds=seq + 10))
    return message


def color_frame(seq: int, mode: int = 1, size=(64, 48)) -> dai.ImgFrame:
    """A uniform ``BGR888i`` frame whose pixels all equal ``mode``."""
    frame = dai.ImgFrame()
    frame.setCvFrame(
        np.full((size[1], size[0], 3), mode, dtype=np.uint8),
        dai.ImgFrame.Type.BGR888i,
    )
    return stamp(frame, seq)


def flat_top_cloud(
    seq: int, size=(64, 48), height=100.0, depth=True, coverage=1.0
) -> dai.PointCloudData:
    """An organized cloud of a plane ``height`` mm above a floor at 1000 mm.

    Without ``depth`` every point is invalid; with ``coverage`` below one,
    every fifth point is.
    """
    width, rows = size
    x, y = np.meshgrid(np.linspace(-200, 200, width), np.linspace(-150, 150, rows))
    points = np.column_stack(
        (x.ravel(), y.ravel(), np.full(width * rows, 1000.0 - height))
    )
    if not depth:
        points[:] = 0
    elif coverage < 1:
        points[::5] = 0
    cloud = dai.PointCloudData()
    cloud.setPoints(points.astype(np.float32))
    return stamp(cloud, seq)


def receive(queue: dai.MessageQueue, timeout: float = 5.0):
    """Poll ``queue`` until a message arrives or ``timeout`` seconds pass."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        message = queue.tryGet()
        if message is not None:
            return message
        time.sleep(0.005)
    raise AssertionError("Timed out awaiting pipeline output")
