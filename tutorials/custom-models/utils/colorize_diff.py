import cv2
import depthai as dai
import numpy as np

DIFF_SHAPE = (720, 720)


class ColorizeDiff(dai.node.HostNode):
    def __init__(self):
        super().__init__()

        self._out = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.ImgFrame, True)
            ]
        )

    def build(self, nn: dai.Node.Output) -> "ColorizeDiff":
        self.link_args(nn)
        return self

    def process(self, nn_data: dai.NNData) -> None:
        frame = self.get_frame(nn_data, DIFF_SHAPE)

        img = dai.ImgFrame()
        img.setCvFrame(frame, dai.ImgFrame.Type.BGR888p)
        # The diff map has the same pixel grid as the NN input frames.
        img.setBufferMetadataFrom(nn_data)
        transformation = nn_data.getTransformation()
        if transformation is not None:
            img.setTransformation(transformation)

        self._out.send(img)

    def get_frame(self, data: dai.NNData, shape):
        diff = (
            data.getFirstTensor(dequantize=True)
            .astype(np.float16)
            .flatten()
            .reshape(shape)
        )
        colorize = cv2.normalize(diff, None, 255, 0, cv2.NORM_INF, cv2.CV_8UC1)
        return cv2.applyColorMap(colorize, cv2.COLORMAP_JET)

    @property
    def out(self):
        return self._out
