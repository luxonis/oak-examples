import depthai as dai
from typing import Optional
from config.config_data_classes import VideoConfig


class CameraSourceNode(dai.node.ThreadedHostNode):
    """
    High-level node for the camera part of the pipeline.

    Internal block:
        Camera
          -> BGR output
          -> NV12 stream -> VideoEncoder -> H.264

    Exposes:
      - preview: BGR888i preview stream.
      - encoded: H.264 encoded stream.
    """

    def __init__(self) -> None:
        super().__init__()

        self._camera: dai.node.Camera = self.createSubnode(dai.node.Camera)
        self._encoder: dai.node.VideoEncoder = self.createSubnode(dai.node.VideoEncoder)

        self.preview: Optional[dai.Node.Output] = None
        self.encoded: dai.Node.Output = self._encoder.out

    def build(self, cfg: VideoConfig) -> "CameraSourceNode":
        """
        @param cfg: Video configuration (resolution, fps, frame type, etc.).
        """
        self._camera.build()  # Camera must be built before requesting outputs

        self.preview = self._camera.requestOutput(
            size=(cfg.width, cfg.height),
            type=cfg.frame_type,
            fps=cfg.fps,
        )

        nv12_out = self._camera.requestOutput(
            size=(cfg.width, cfg.height),
            type=dai.ImgFrame.Type.NV12,
            fps=cfg.fps,
        )

        self._encoder.setDefaultProfilePreset(
            fps=cfg.fps,
            profile=dai.VideoEncoderProperties.Profile.H264_MAIN,
        )
        nv12_out.link(self._encoder.input)

        return self

    def run(self) -> None:
        # High-level node: no host-side processing, everything runs in subnodes.
        pass
