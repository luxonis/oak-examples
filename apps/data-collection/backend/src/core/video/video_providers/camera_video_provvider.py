import depthai as dai

from config.config_data_classes import VideoConfig
from core.video.video_providers.base_video_provider import BaseVideoProvider


class CameraVideoProvider(BaseVideoProvider):
    """Video source from live DepthAI camera."""

    def __init__(self, pipeline: dai.Pipeline, config: VideoConfig):
        super().__init__(pipeline, config)
        self._camera: dai.node.Camera = self._build_camera()

    def get_video_node(self) -> dai.Node.Output:
        return self._camera.requestOutput(
            size=(self._config.width, self._config.height),
            type=dai.ImgFrame.Type.BGR888i,
            fps=self._config.fps,
        )

    def get_nv12_output(self) -> dai.Node.Output:
        return self._camera.requestOutput(
            size=self._config.resolution,
            type=dai.ImgFrame.Type.NV12,
            fps=self._config.fps,
        )

    def _build_camera(self) -> dai.node.Camera:
        return self._pipeline.create(dai.node.Camera).build(
            boardSocket=dai.CameraBoardSocket.CAM_A
        )
