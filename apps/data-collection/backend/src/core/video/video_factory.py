import depthai as dai
from config.config_data_classes import VideoConfig
from core.video.video_providers.base_video_provider import BaseVideoProvider
from core.video.video_providers.camera_video_provvider import (
    CameraVideoProvider,
)
from core.video.video_providers.replay_video_provider import (
    ReplayVideoProvider,
)


class VideoFactory:
    """Facade that chooses the right source type and provides encoder."""

    def __init__(self, pipeline: dai.Pipeline, cfg: VideoConfig):
        self._pipeline: dai.Pipeline = pipeline
        self._config: VideoConfig = cfg
        self._source: BaseVideoProvider = self._select_source()

    def _select_source(self) -> BaseVideoProvider:
        if self._config.media_path:
            return ReplayVideoProvider(self._pipeline, self._config)
        return CameraVideoProvider(self._pipeline, self._config)

    def get_video_node(self) -> dai.Node.Output:
        return self._source.get_video_node()

    def get_nv12_output(self) -> dai.Node.Output:
        return self._source.get_nv12_output()

    def get_encoded_output(self) -> dai.Node.Output:
        """Attach H.264 encoder to NV12 output."""
        encoder = self._pipeline.create(dai.node.VideoEncoder)
        encoder.setDefaultProfilePreset(
            fps=self._config.fps,
            profile=dai.VideoEncoderProperties.Profile.H264_MAIN,
        )
        self.get_nv12_output().link(encoder.input)
        return encoder.out
