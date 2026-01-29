import depthai as dai
import numpy as np


class FrameCacheNode(dai.node.HostNode):
    """
    Host node that caches the latest ImgFrame as a NumPy BGR image for prompt services.
    """

    def __init__(self) -> None:
        super().__init__()
        self._last_frame: np.ndarray | None = None

    def build(self, input_frame: dai.Node.Output) -> "FrameCacheNode":
        self.link_args(input_frame)
        return self

    def process(self, input_frame: dai.ImgFrame) -> dai.ImgFrame:
        self._last_frame = input_frame.getCvFrame()
        return input_frame

    def get_last_frame(self) -> np.ndarray | None:
        return self._last_frame
