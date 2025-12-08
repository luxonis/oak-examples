import depthai as dai
from pathlib import Path


class VideoProvider:
    """
    Provides the main input video stream and handles final encoding.
    """

    def __init__(self, pipeline, platform, fps_limit=None, media_path=None):
        self.pipeline = pipeline
        self.platform = platform
        self.fps_limit = fps_limit
        self.media_path = media_path

        self._input = self._create_input()
        self._main_stream = self._create_main_stream()

        self._encoder = None
        self.encoded = None

    def _create_input(self):
        if self.media_path:
            return self._create_replay_node()
        else:
            return self._create_camera_node()

    def _create_replay_node(self):
        rv = self.pipeline.create(dai.node.ReplayVideo)
        rv.setReplayVideoFile(Path(self.media_path))

        if self.platform == "RVC2":
            rv.setOutFrameType(dai.ImgFrame.Type.BGR888p)
        elif self.platform == "RVC4":
            rv.setOutFrameType(dai.ImgFrame.Type.BGR888i)
        else:
            raise ValueError(f"ReplayVideo not supported on {self.platform}")
        return rv

    def _create_camera_node(self):
        cam = self.pipeline.create(dai.node.Camera)
        return cam.build()

    def _create_main_stream(self):
        return self._input.requestOutput(
            size=(1280, 720),
            type=dai.ImgFrame.Type.BGR888i,
            fps=self.fps_limit,
        )

    def get_main_stream(self):
        return self._main_stream

    def encode(self, video: dai.Node.Output) -> dai.Node.Output:
        manip = self.pipeline.create(dai.node.ImageManip)
        manip.initialConfig.setOutputSize(1280, 720)
        manip.initialConfig.setFrameType(dai.ImgFrame.Type.NV12)
        manip.setMaxOutputFrameSize(int(1280 * 720 * 3))
        video.link(manip.inputImage)

        enc = self.pipeline.create(dai.node.VideoEncoder)
        enc.setDefaultProfilePreset(30, dai.VideoEncoderProperties.Profile.H264_MAIN)
        manip.out.link(enc.input)

        return enc.out
