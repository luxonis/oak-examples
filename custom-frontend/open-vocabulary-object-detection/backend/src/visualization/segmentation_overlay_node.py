from typing import Optional

import depthai as dai
from depthai_nodes.node import ApplyColormap, InstanceToSemanticMask, ImgFrameOverlay

from config.config_data_classes import VideoConfig


class SegmentationOverlayNode(dai.node.ThreadedHostNode):
    """
    High-level node for YOLOE segmentation visualization.

    Internal block:
        detections (NN output)
          -> InstanceToSemanticMask (optional if semantic = True) - converts instance to semantic mask
          -> ApplyColormap
          -> ImgFrameOverlay
          -> ImageManip (to NV12)
          -> VideoEncoder -> H.264 stream

    Inputs:
        - input_detections: dai.Node.Output (parsed NN output)
        - input_frame: dai.Node.Output BGR source frames used as the background
        - semantic: bool (True = instance -> semantic mask conversion before colormap)

    Exposes:
        - encoded: dai.Node.Output (H.264 encoded overlay video stream)
    """

    def __init__(self) -> None:
        super().__init__()

        self._instance_to_semantic: Optional[InstanceToSemanticMask] = None
        self._apply_colormap = self.createSubnode(ApplyColormap)
        self._img_overlay = self.createSubnode(ImgFrameOverlay)
        self._img_manip = self.createSubnode(dai.node.ImageManip)
        self._encoder = self.createSubnode(dai.node.VideoEncoder)

        self.encoded: dai.Node.Output = None

    def build(
        self,
        input_frame: dai.Node.Output,
        input_detections: dai.Node.Output,
        semantic: bool,
        cfg: VideoConfig,
    ) -> "SegmentationOverlayNode":
        w, h = cfg.width, cfg.height

        if semantic:
            self._instance_to_semantic = self.createSubnode(InstanceToSemanticMask)
            self._instance_to_semantic.build(input_detections)
            mask_src = self._instance_to_semantic.out
        else:
            mask_src = input_detections

        self._apply_colormap.build(mask_src)

        self._img_overlay.build(
            frame1=input_frame,
            frame2=self._apply_colormap.out,
            preserve_background=True,
        )

        self._img_manip.setMaxOutputFrameSize(w * h * 3)
        self._img_manip.initialConfig.setFrameType(dai.ImgFrame.Type.NV12)
        self._img_overlay.out.link(self._img_manip.inputImage)

        self._encoder.setDefaultProfilePreset(
            fps=cfg.fps,
            profile=dai.VideoEncoderProperties.Profile.H264_MAIN,
        )
        self._img_manip.out.link(self._encoder.input)

        self.encoded = self._encoder.out
        return self

    def run(self) -> None:
        # High-level node: subnodes handle all processing.
        pass
