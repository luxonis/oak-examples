import depthai as dai

from box import Box


class Encoder:
    def __init__(self, pipeline: dai.Pipeline, config: Box):
        self.pipeline = pipeline
        self.output_w = config.resolution[0]
        self.output_h = config.resolution[1]
        self.fps = config.fps

    def encode(self, video: dai.Node.Output) -> dai.Node.Output:
        manip = self.pipeline.create(dai.node.ImageManip)
        manip.initialConfig.setOutputSize(self.output_w, self.output_h)
        manip.initialConfig.setFrameType(dai.ImgFrame.Type.NV12)
        manip.setMaxOutputFrameSize(int(self.output_w * self.output_h * 3))
        video.link(manip.inputImage)

        enc = self.pipeline.create(dai.node.VideoEncoder)
        enc.setDefaultProfilePreset(
            self.fps, dai.VideoEncoderProperties.Profile.H264_MAIN
        )
        manip.out.link(enc.input)

        return enc.out
