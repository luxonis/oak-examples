from pathlib import Path
from typing import Optional

import depthai as dai

from config.config_data_classes import VideoConfig


class CameraSourceNode(dai.node.ThreadedHostNode):
    """
    High-level node for the camera part of the pipeline.

    Internal block:
        Camera
          -> BGR output
          -> NV12 stream -> VideoEncoder -> H.264

    Handles both live camera and file replay sources, exposing:
      - bgr: BGR888i stream.
      - encoded: H.264 encoded stream.

    """

    def __init__(self) -> None:
        super().__init__()

        self._encoder: dai.node.VideoEncoder = self.createSubnode(dai.node.VideoEncoder)

        self._camera: Optional[dai.node.Camera] = None
        self._replay: Optional[dai.node.ReplayVideo] = None
        self._manip: Optional[dai.node.ImageManip] = None

        self._nv12_out: Optional[dai.Node.Output] = None
        self.bgr: Optional[dai.Node.Output] = None
        self.encoded: Optional[dai.Node.Output] = None

    def build(self, cfg: VideoConfig) -> "CameraSourceNode":
        """
        @param cfg: Video configuration with resolution, fps, and optional media_path.
        """
        if cfg.media_path:
            self._setup_replay(cfg)
        else:
            self._setup_camera(cfg)

        self._setup_encoder(cfg)
        return self

    def _setup_camera(self, cfg: VideoConfig) -> None:
        """Configure live camera source."""
        self._camera = self.createSubnode(dai.node.Camera)
        self._camera.build()

        self.bgr = self._camera.requestOutput(
            size=(cfg.width, cfg.height),
            type=dai.ImgFrame.Type.BGR888i,
            fps=cfg.fps,
        )

        self._nv12_out = self._camera.requestOutput(
            size=(cfg.width, cfg.height),
            type=dai.ImgFrame.Type.NV12,
            fps=cfg.fps,
        )

    def _setup_replay(self, cfg: VideoConfig) -> None:
        """Configure file replay source."""
        self._replay = self.createSubnode(dai.node.ReplayVideo)
        self._replay.setReplayVideoFile(Path(cfg.media_path))
        self._replay.setOutFrameType(dai.ImgFrame.Type.NV12)
        self._replay.setLoop(True)
        self._replay.setFps(cfg.fps)
        self._replay.setSize((cfg.width, cfg.height))

        # ImageManip to convert NV12 to BGR
        self._manip = self.createSubnode(dai.node.ImageManip)
        self._manip.setMaxOutputFrameSize(cfg.width * cfg.height * 3)
        self._manip.initialConfig.setOutputSize(cfg.width, cfg.height)
        self._manip.initialConfig.setFrameType(dai.ImgFrame.Type.BGR888i)
        self._replay.out.link(self._manip.inputImage)

        self.bgr = self._manip.out
        self._nv12_out = self._replay.out

    def _setup_encoder(self, cfg: VideoConfig) -> None:
        """Configure H.264 encoder for visualization."""
        self._encoder.setDefaultProfilePreset(
            fps=cfg.fps,
            profile=dai.VideoEncoderProperties.Profile.H264_MAIN,
        )
        self._nv12_out.link(self._encoder.input)
        self.encoded = self._encoder.out

    def run(self) -> None:
        # High-level node: subnodes handle all processing.
        pass
