from typing import Optional, Tuple

import depthai as dai


class CropConfigsCreator(dai.node.HostNode):
    """Create upright recognition crops from filtered rotated text detections.

    Expanded rotated boxes are cropped and letterboxed with white padding by
    default. The axis-aligned outer box is used only for the minimum-size check.

    To ensure correct synchronization between the crop configurations and the image,
    ensure "inputConfig.setReusePreviousMessage" is set to False in the dai.ImageManip node.

    Attributes
    ----------
    detections_input : dai.Input
        The input link for the dai.ImgDetections message.
    config_output : dai.Output
        The output link for the ImageManipConfig messages.
    detections_output : dai.Output
        The output link for the dai.ImgDetections message.
    source : dai.Node.Output
        Source frames or metadata frames defining the recognition crop space.
    target_size : Optional[Tuple[int, int]] = None
        The size of the target image (width, height). If None, crop sizes will not be uniform.
    resize_mode : dai.ImageManipConfig.ResizeMode = dai.ImageManipConfig.ResizeMode.LETTERBOX
        The resize mode to use when target size is set. Options are: CENTER_CROP, LETTERBOX, NONE, STRETCH.
    confidence_threshold : float = 0.5
        Keep detections above this confidence.
    min_crop_width, min_crop_height : int = 50, 12
        Minimum expanded outer-box dimensions in source pixels.
    """

    def __init__(self) -> None:
        """Initializes the node."""
        super().__init__()
        self.inputs["source"].getParent().setTimestampSource(
            dai.node.Sync.TimestampSource.DEVICE
        )
        self.config_output = self.createOutput()
        self.detections_output = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.Buffer, True)
            ]
        )
        self._target_w: int = None
        self._target_h: int = None
        self.resize_mode: dai.ImageManipConfig.ResizeMode = None
        self.confidence_threshold: float = 0.5
        self.min_crop_width: int = 50
        self.min_crop_height: int = 12

    @property
    def target_w(self) -> int:
        return self._target_w

    @property
    def target_h(self) -> int:
        return self._target_h

    @target_w.setter
    def target_w(self, target_w: int):
        self._validate_positive_integer(target_w)
        self._target_w = target_w

    @target_h.setter
    def target_h(self, target_h: int):
        self._validate_positive_integer(target_h)
        self._target_h = target_h

    def build(
        self,
        detections_input: dai.Node.Output,
        source: dai.Node.Output,
        target_size: Optional[Tuple[int, int]] = None,
        resize_mode: dai.ImageManipConfig.ResizeMode = dai.ImageManipConfig.ResizeMode.LETTERBOX,
        confidence_threshold: float = 0.5,
        min_crop_width: int = 50,
        min_crop_height: int = 12,
    ) -> "CropConfigsCreator":
        """Link the node input and set the correct source and target image sizes.

        Parameters
        ----------
        detections_input : dai.Node.Output
            The input link for the dai.ImgDetections message
        source : dai.Node.Output
            Original source frames, or metadata frames with their size and transformation.
        target_size : Optional[Tuple[int, int]]
            The size of the target image (width, height). If None, crop sizes will not be uniform.
        resize_mode : dai.ImageManipConfig.ResizeMode = dai.ImageManipConfig.ResizeMode.LETTERBOX
            The resize mode to use when target size is set. Options are: CENTER_CROP, LETTERBOX, NONE, STRETCH.
        confidence_threshold : float
            Keep detections above this confidence.
        min_crop_width, min_crop_height : int
            Minimum expanded outer-box dimensions in source pixels.
        """

        if target_size is not None:
            self.target_w = target_size[0]
            self.target_h = target_size[1]

        if not 0 <= confidence_threshold <= 1:
            raise ValueError("confidence_threshold must be between 0 and 1")
        if min_crop_width < 1 or min_crop_height < 1:
            raise ValueError("Minimum crop dimensions must be positive")

        self.resize_mode = resize_mode
        self.confidence_threshold = confidence_threshold
        self.min_crop_width = min_crop_width
        self.min_crop_height = min_crop_height

        self.link_args(detections_input, source)

        return self

    def process(
        self, detections_input: dai.ImgDetections, source: dai.ImgFrame
    ) -> None:
        """Process the input detections and create crop configurations. This function is
        ran every time a new dai.ImgDetections message is
        received.

        Sends len(detections) number of crop configurations to the config_output link.
        In addition sends a dai.ImgDetections object containing the corresponding
        detections to the detections_output link.
        """

        assert isinstance(detections_input, dai.ImgDetections)

        width, height = source.getWidth(), source.getHeight()
        detections = detections_input.detections

        configs_group = dai.MessageGroup()
        valid_detections = []
        for detection in detections:
            if detection.confidence > self.confidence_threshold:
                rect = detection.getBoundingBox()
                rect.size = dai.Size2f(
                    rect.size.width * 1.03, rect.size.height * 1.10, True
                )
                rect = detections_input.getTransformation().remapRectTo(
                    source.getTransformation(), rect
                )
                # Rotated outer bounds must be calculated in source pixels.
                xmin, ymin, xmax, ymax = rect.denormalize(width, height).getOuterRect()
                xmin = int(max(0, xmin))
                ymin = int(max(0, ymin))
                xmax = int(min(width, xmax))
                ymax = int(min(height, ymax))

                if (
                    xmax - xmin < self.min_crop_width
                    or ymax - ymin < self.min_crop_height
                ):
                    continue

                valid_detections.append(detection)

                cfg = dai.ImageManipConfig()
                cfg.addCropRotatedRect(rect, normalizedCoords=True)
                cfg.setBackgroundColor(255, 255, 255)

                if self.target_w is not None and self.target_h is not None:
                    cfg.setOutputSize(self.target_w, self.target_h, self.resize_mode)

                cfg.setBufferMetadataFrom(detections_input)
                # MessageGroup iterates keys lexicographically. Fixed-width keys
                # keep crop output order aligned with valid_detections at 10+ boxes.
                configs_group[f"cfg_{len(valid_detections) - 1:05d}"] = cfg

        configs_group.setBufferMetadataFrom(detections_input)
        self.config_output.send(configs_group)

        valid_msg = dai.ImgDetections()
        valid_msg.setBufferMetadataFrom(detections_input)
        valid_msg.detections = valid_detections
        valid_msg.setTransformation(detections_input.getTransformation())

        self.detections_output.send(valid_msg)

    def _validate_positive_integer(self, value: int) -> None:
        if not isinstance(value, int) or value <= 0:
            raise ValueError(f"Expected a positive integer, got {value!r}")
