import cv2
import depthai as dai


class RectifiedColor(dai.node.HostNode):
    """Replicate rectified RAW8 into model color channels without changing geometry.

    RVC4 ImageManip does not accept StereoDepth RAW8 for color conversion.
    """

    def __init__(self):
        super().__init__()
        self.output = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.ImgFrame, True)
            ]
        )

    def build(self, rectified: dai.Node.Output, frame_type):
        self.link_args(rectified)
        self.frame_type = frame_type
        return self

    def process(self, rectified: dai.ImgFrame):
        pixels = cv2.cvtColor(rectified.getCvFrame(), cv2.COLOR_GRAY2BGR)
        frame = dai.ImgFrame()
        frame.setCvFrame(pixels, self.frame_type)
        frame.setBufferMetadataFrom(rectified)
        frame.setInstanceNum(rectified.getInstanceNum())
        frame.setTransformation(rectified.getTransformation())
        self.output.send(frame)
