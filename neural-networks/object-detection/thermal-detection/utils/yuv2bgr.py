import depthai as dai


class YUV2BGR(dai.node.ThreadedHostNode):
    def __init__(self):
        super().__init__()
        self.input = self.createInput()
        self.out = self.createOutput()

    def run(self):
        while self.isRunning():
            source = self.input.get()
            frame = dai.ImgFrame()
            frame.setCvFrame(source.getCvFrame(), dai.ImgFrame.Type.BGR888p)
            frame.setBufferMetadataFrom(source)
            frame.setTransformation(source.getTransformation())
            self.out.send(frame)
