import depthai as dai
from depthai_nodes.node import ImgDetectionsBridge
from depthai_nodes import ImgDetectionsExtended


class SafeImgDetectionsExtendedBridge(ImgDetectionsBridge):
    """
    Type-aware ImgDetectionsBridge: only converts when input is ImgDetections.
    Otherwise, forwards the message as-is.
    """

    def process(self, msg: dai.Buffer) -> None:
        if isinstance(msg, ImgDetectionsExtended):
            super().process(msg)
            return
        else:
            self.out.send(msg)
