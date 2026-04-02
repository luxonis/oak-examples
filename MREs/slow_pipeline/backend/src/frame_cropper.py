from string import Template
from typing import Optional, Tuple

import depthai as dai

from depthai_nodes.node.base_threaded_host_node import BaseThreadedHostNode


class FrameCropper(BaseThreadedHostNode):
    """A host node that crops detection regions from frames and outputs one cropped
    :class:`dai.ImgFrame` per region.

    `FrameCropper` is a convenience wrapper around an internal
    :class:`dai.node.ImageManip` configured for cropping + resizing. It supports
    two input modes:

    - **fromImgDetections**: Provide :class:`dai.ImgDetections`
      and the node will generate :class:`dai.ImageManipConfig` messages for each
      detection via a :class:`dai.node.Script` node. Each config is paired with
      the corresponding input frame, producing one cropped output frame per
      detection.
    - **fromManipConfigs**: Provide an upstream stream of cropping configs packed
      in :class:`dai.MessageGroup` messages. An on-device :class:`dai.node.Script`
      node pairs each config with the current frame and forwards them to the
      internal :class:`dai.node.ImageManip`.

    Configuration is provided via :meth:`fromImgDetections` or
    :meth:`fromManipConfigs`. The pipeline nodes are constructed only once
    :meth:`build` is called.

    Notes
    -----
    - Exactly one configuration path must be selected: only one of
      :meth:`fromImgDetections` and :meth:`fromManipConfigs` can be used.
    - Output frames are always resized to `outputSize` using the provided
      `resizeMode` (default: ``CENTER_CROP``).
    - In `fromImgDetections` mode, a :class:`dai.node.Script` node drives the
      cropping by emitting one :class:`dai.ImageManipConfig` per detection.
    - In `fromManipConfigs` mode, the `inputManipConfigs` stream **must**
      output :class:`dai.MessageGroup` messages where each value is a
      :class:`dai.ImageManipConfig`. Key naming is arbitrary.

    Parameters
    ----------
    fromImgDetections(padding=0.0)
        Optional padding factor applied around each detection region.
    build(outputSize, resizeMode)
        Sets the crop output size and the resize mode used by ImageManip.

    Outputs
    -------
    out : dai.Node.Output
        Stream of cropped :class:`dai.ImgFrame` messages. One output frame is
        produced per crop configuration (per detection in `fromImgDetections`
        mode; per config in the received `MessageGroup` in `fromManipConfigs` mode).

    See Also
    --------
    dai.node.ImageManip
        Node used to perform cropping and resizing.
    dai.ImageManipConfig
        Cropping configuration messages forwarded to ImageManip.
    dai.ImgDetections
        Detection message type used in `fromImgDetections` mode.
    dai.MessageGroup
        Message type expected by `fromManipConfigs`.
    """

    IMG_DETECTIONS_SCRIPT_CONTENT = Template(
        """
        def pad_rotated_rect(rot: RotatedRect, p: float) -> RotatedRect:
            return RotatedRect(
                rot.center,
                Size2f(width=rot.size.width + 2*p, height=rot.size.height + 2*p, normalized=True),
                rot.angle
            )
        try:
            OUT_WIDTH = $OUT_WIDTH
            OUT_HEIGHT = $OUT_HEIGHT
            PADDING = $PADDING
            FRAME_TYPE = ImgFrame.Type.$FRAME_TYPE
            RESIZE_MODE = ImageManipConfig.ResizeMode.$RESIZE_MODE
            while True:
                # We receive 1 detection count message and image per frame
                frame = node.inputs['inputImage'].get()
                img_detections = node.inputs['inputImgDetections'].get()
                for det in img_detections.detections:
                    rot_rect = det.getBoundingBox()
                    cfg = ImageManipConfig()
                    cfg.addCropRotatedRect(rect=pad_rotated_rect(rot_rect, PADDING), normalizedCoords=True)
                    cfg.setTimestamp(img_detections.getTimestamp())
                    cfg.setTimestampDevice(img_detections.getTimestampDevice())
                    cfg.setSequenceNum(img_detections.getSequenceNum())
                    cfg.setOutputSize(OUT_WIDTH, OUT_HEIGHT, RESIZE_MODE)
                    cfg.setFrameType(FRAME_TYPE)
                    node.outputs['manip_cfg'].send(cfg)
                    node.outputs['manip_img'].send(frame)

        except Exception as e:
            node.error(str(e))
        """
    )

    MANIP_CONFIGS_SCRIPT_CONTENT = """
        try:
            while True:
                frame = node.inputs['inputImage'].get()
                configs = node.inputs['inputManipConfigs'].get()
                for key, cfg in configs:
                    node.outputs['manip_cfg'].send(cfg)
                    node.outputs['manip_img'].send(frame)
        except Exception as e:
            node.error(str(e))
        """

    def __init__(self):
        super().__init__()
        self._cropper_image_manip = self._pipeline.create(dai.node.ImageManip)
        self._version_selected = False
        self._output_size: Optional[Tuple[int, int]] = None  # width, height

        # when fromImgDetections is used script node can work on ImgDetections directly
        self._script: Optional[dai.node.Script] = None
        self._input_img_detections: Optional[dai.Node.Output] = None
        self._padding: Optional[float] = None

        # when fromManipConfigs is used, script node receives MessageGroup of precomputed configs
        self._input_manip_configs: Optional[dai.Node.Output] = None
        self._logger.debug("FrameCropper initialized")

    @property
    def out(self):
        """Return the cropped frame output stream."""
        return self._cropper_image_manip.out

    def fromImgDetections(
        self, inputImgDetections: dai.Node.Output, padding: float = 0.0
    ) -> "FrameCropper":
        """Configure cropping from an ImgDetections stream.

        In this mode the node generates ImageManipConfig messages per detection (via Script)
        and outputs one cropped ImgFrame per detection. `padding` expands the crop region.
        """
        if self._version_selected is True:
            raise RuntimeError(
                "FrameCropper was already configured using the `fromManipConfigs` method. "
                "Only one of `fromImgDetections` and `fromManipConfigs` can be used."
            )
        self._version_selected = True
        self._input_img_detections = inputImgDetections
        self._padding = padding
        return self

    def fromManipConfigs(self, inputManipConfigs: dai.Node.Output) -> "FrameCropper":
        """Configure cropping from a stream of precomputed ImageManipConfig groups.

        Expects `inputManipConfigs` to output dai.MessageGroup messages where each
        value is an ImageManipConfig. An on-device Script node pairs each config with
        the current frame and forwards them to ImageManip.

        Key naming is arbitrary; all values in the MessageGroup are treated as configs.
        """
        if self._version_selected is True:
            raise RuntimeError(
                "FrameCropper was already configured using the `fromManipConfig` method. "
                "Only one of `fromImgDetections` and `fromManipConfigs` can be used."
            )
        self._version_selected = True
        self._input_manip_configs = inputManipConfigs
        return self

    def build(
        self,
        inputImage: dai.Node.Output,
        outputSize: Tuple[int, int],
        resizeMode: dai.ImageManipConfig.ResizeMode = dai.ImageManipConfig.ResizeMode.CENTER_CROP,
    ) -> "FrameCropper":
        """Build the internal pipeline and set output size / resize behavior.

        Requires that exactly one configuration path was selected via `fromImgDetections`
        or `fromManipConfigs` before calling. Returns `self` for fluent chaining.
        """
        if self._version_selected is False:
            raise RuntimeError(
                "Configure the FrameCropper by calling one of the `fromImgDetections` or `fromManipConfigs` methods first."
            )
        self._output_size = outputSize
        self._cropper_image_manip.setMaxOutputFrameSize(
            self._output_size[0] * self._output_size[1] * 3
        )
        self._cropper_image_manip.initialConfig.setOutputSize(
            *self._output_size, mode=resizeMode
        )
        self._cropper_image_manip.inputConfig.setWaitForMessage(waitForMessage=True)
        if self._input_img_detections is not None:
            self._build_detections_cropper(
                input_image=inputImage, resize_mode=resizeMode
            )
        else:
            self._build_manip_configs_cropper(input_image=inputImage)
        self._logger.debug("FrameCropper built")
        return self

    def run(self) -> None:
        """No-op because cropping is driven entirely by on-device Script nodes."""
        return  # Both fromImgDetections and fromManipConfigs use on-device Script

    def _build_detections_cropper(
        self, input_image: dai.Node.Output, resize_mode: dai.ImageManipConfig.ResizeMode
    ):
        self._script = self._pipeline.create(dai.node.Script)
        self._script.setScript(
            self.IMG_DETECTIONS_SCRIPT_CONTENT.substitute(
                {
                    "OUT_WIDTH": self._output_size[0],
                    "OUT_HEIGHT": self._output_size[1],
                    "PADDING": self._padding,
                    "FRAME_TYPE": self._img_frame_type.name,
                    "RESIZE_MODE": resize_mode.name,
                }
            )
        )
        input_image.link(self._script.inputs["inputImage"])
        self._input_img_detections.link(self._script.inputs["inputImgDetections"])
        self._script.outputs["manip_cfg"].link(self._cropper_image_manip.inputConfig)
        self._script.outputs["manip_img"].link(self._cropper_image_manip.inputImage)

    def _build_manip_configs_cropper(self, input_image: dai.Node.Output):
        self._script = self._pipeline.create(dai.node.Script)
        self._script.setScript(self.MANIP_CONFIGS_SCRIPT_CONTENT)
        input_image.link(self._script.inputs["inputImage"])
        self._input_manip_configs.link(self._script.inputs["inputManipConfigs"])
        self._script.outputs["manip_cfg"].link(self._cropper_image_manip.inputConfig)
        self._script.outputs["manip_img"].link(self._cropper_image_manip.inputImage)
