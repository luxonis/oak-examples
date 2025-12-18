import depthai as dai
from box import Box


class Encoder:
    def __init__(self, pipeline: dai.Pipeline, config: Box):
        self._pipeline = pipeline
        self._output_w = config.resolution[0]
        self._output_h = config.resolution[1]
        self._fps = config.fps

    def encode(self, video: dai.Node.Output) -> dai.Node.Output:
        manip = self._pipeline.create(dai.node.ImageManip)
        manip.initialConfig.setOutputSize(self._output_w, self._output_h)
        manip.initialConfig.setFrameType(dai.ImgFrame.Type.NV12)
        manip.setMaxOutputFrameSize(int(self._output_w * self._output_h * 3))
        video.link(manip.inputImage)

        enc = self._pipeline.create(dai.node.VideoEncoder)
        enc.setDefaultProfilePreset(
            self._fps, dai.VideoEncoderProperties.Profile.H264_MAIN
        )
        manip.out.link(enc.input)

        return enc.out
