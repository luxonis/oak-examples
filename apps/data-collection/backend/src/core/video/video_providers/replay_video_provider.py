from pathlib import Path

from config.config_data_classes import VideoConfig
from core.video.video_providers.base_video_provider import BaseVideoProvider
import depthai as dai


class ReplayVideoProvider(BaseVideoProvider):
    """Video source from file replay."""

    def __init__(self, pipeline: dai.Pipeline, config: VideoConfig):
        super().__init__(pipeline, config)
        self._replay: dai.node.ReplayVideo = self._build_replay()

    def get_video_node(self) -> dai.Node.Output:
        manip = self._pipeline.create(dai.node.ImageManip)
        manip.setMaxOutputFrameSize(self._config.width * self._config.height * 3)
        manip.initialConfig.setOutputSize(self._config.width, self._config.height)
        manip.initialConfig.setFrameType(dai.ImgFrame.Type.BGR888i)
        self._replay.out.link(manip.inputImage)
        return manip.out

    def get_nv12_output(self) -> dai.Node.Output:
        return self._replay.out

    def _build_replay(self) -> dai.node.ReplayVideo:
        replay = self._pipeline.create(dai.node.ReplayVideo)
        replay.setReplayVideoFile(Path(self._config.media_path))
        replay.setOutFrameType(dai.ImgFrame.Type.NV12)
        replay.setLoop(True)
        replay.setFps(self._config.fps)
        replay.setSize(self._config.resolution)
        return replay
