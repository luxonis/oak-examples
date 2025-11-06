import depthai as dai
import numpy as np


class FrameCacheNode(dai.node.HostNode):
    def __init__(self) -> None:
        super().__init__()
        self._last_frame: np.ndarray | None = None

    def build(self, frame: dai.Node.Output) -> "FrameCacheNode":
        self.link_args(frame)
        return self

    def process(self, frame: dai.ImgFrame) -> dai.ImgFrame:
        self._last_frame = frame.getCvFrame()
        return frame

    def get_last_frame(self) -> np.ndarray | None:
        return self._last_frame
