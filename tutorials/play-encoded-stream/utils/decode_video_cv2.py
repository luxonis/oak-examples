import cv2
import depthai as dai


class DecodeVideoCV2(dai.node.HostNode):
    def __init__(self) -> None:
        super().__init__()

        self._out = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.ImgFrame, True)
            ]
        )

    def build(self, enc_out) -> "DecodeVideoCV2":
        self.link_args(enc_out)
        return self

    def process(self, enc_vid: dai.ImgFrame) -> None:
        frame = cv2.imdecode(enc_vid.getData(), cv2.IMREAD_COLOR)
        if frame is None:
            return  # corrupt or truncated JPEG

        img = dai.ImgFrame()
        img.setCvFrame(frame, dai.ImgFrame.Type.NV12)
        # Each MJPEG message decodes to one frame with the same pixel grid.
        img.setBufferMetadataFrom(enc_vid)
        img.setTransformation(enc_vid.getTransformation())

        self.out.send(img)

    @property
    def out(self) -> dai.Node.Output:
        return self._out
