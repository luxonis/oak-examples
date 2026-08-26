import logging
import threading
import time
from typing import Optional, Tuple

import depthai as dai
import numpy as np
from inference.core.interfaces.camera.entities import (
    SourceProperties,
    VideoFrameProducer,
)


class DepthAIFrameProducer(VideoFrameProducer):
    """
    Feeds DepthAI camera frames into Roboflow's `InferencePipeline`.

    Implements the official `VideoFrameProducer` interface, so a factory creating
    this producer can be passed directly as `video_reference` to
    `InferencePipeline.init_with_workflow(...)`.
    """

    # How long `grab()` waits for a new frame before reporting the source as drained.
    _GRAB_TIMEOUT_S = 5.0

    def __init__(self, queue: dai.MessageQueue, width: int, height: int, fps: float):
        self._queue = queue
        self._width = width
        self._height = height
        self._fps = fps
        self._frame: Optional[np.ndarray] = None
        self._closed = threading.Event()
        self._logger = logging.getLogger(self.__class__.__name__)

    def grab(self) -> bool:
        deadline = time.monotonic() + self._GRAB_TIMEOUT_S
        while not self._closed.is_set() and time.monotonic() < deadline:
            try:
                message = self._queue.tryGet()
            except dai.MessageQueue.QueueException:
                break
            if message is not None:
                self._frame = message.getCvFrame()
                return True
            time.sleep(0.005)
        return False

    def retrieve(self) -> Tuple[bool, Optional[np.ndarray]]:
        if self._frame is None:
            return False, None
        return True, self._frame

    def isOpened(self) -> bool:
        return not self._closed.is_set()

    def release(self):
        self._closed.set()
        self._logger.info("DepthAI frame producer released")

    def discover_source_properties(self) -> SourceProperties:
        return SourceProperties(
            width=self._width,
            height=self._height,
            total_frames=-1,
            is_file=False,
            fps=self._fps,
        )
