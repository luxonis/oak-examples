from typing import Optional, Tuple

import depthai as dai


class CropConfigsCreator(dai.node.HostNode):
    """A node to create and send a dai.ImageManipConfig crop configuration for each
    detection in a list of detections. An optional target size and resize mode can be
    set to ensure uniform crop sizes.

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
    source_size : Tuple[int, int]
        The size of the source image (width, height).
    target_size : Optional[Tuple[int, int]] = None
        The size of the target image (width, height). If None, crop sizes will not be uniform.
    resize_mode : dai.ImageManipConfig.ResizeMode = dai.ImageManipConfig.ResizeMode.STRETCH
        The resize mode to use when target size is set. Options are: CENTER_CROP, LETTERBOX, NONE, STRETCH.
    """

    def __init__(self) -> None:
        """Initializes the node."""
        super().__init__()
        self.config_output = self.createOutput()
        self.detections_output = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.Buffer, True)
            ]
        )
        self._w: int = None
        self._h: int = None
        self._target_w: int = None
        self._target_h: int = None
        self.resize_mode: dai.ImageManipConfig.ResizeMode = None

    @property
    def w(self) -> int:
        return self._w

    @property
    def h(self) -> int:
        return self._h

    @property
    def target_w(self) -> int:
        return self._target_w

    @property
    def target_h(self) -> int:
        return self._target_h

    @w.setter
    def w(self, w: int):
        self._validate_positive_integer(w)
        self._w = w

    @h.setter
    def h(self, h: int):
        self._validate_positive_integer(h)
        self._h = h

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
        source_size: Tuple[int, int],
        target_size: Optional[Tuple[int, int]] = None,
        resize_mode: dai.ImageManipConfig.ResizeMode = dai.ImageManipConfig.ResizeMode.STRETCH,
    ) -> "CropConfigsCreator":
        """Link the node input and set the correct source and target image sizes.

        Parameters
        ----------
        detections_input : dai.Node.Output
            The input link for the dai.ImgDetections message
        source_size : Tuple[int, int]
            The size of the source image (width, height).
        target_size : Optional[Tuple[int, int]]
            The size of the target image (width, height). If None, crop sizes will not be uniform.
        resize_mode : dai.ImageManipConfig.ResizeMode = dai.ImageManipConfig.ResizeMode.STRETCH
            The resize mode to use when target size is set. Options are: CENTER_CROP, LETTERBOX, NONE, STRETCH.
        """

        self.w = source_size[0]
        self.h = source_size[1]

        if target_size is not None:
            self.target_w = target_size[0]
            self.target_h = target_size[1]

        self.resize_mode = resize_mode

        self.link_args(detections_input)

        return self

    def process(self, detections_input: dai.Buffer) -> None:
        """Process the input detections and create crop configurations. This function is
        ran every time a new dai.ImgDetections message is
        received.

        Sends len(detections) number of crop configurations to the config_output link.
        In addition sends a dai.ImgDetections object containing the corresponding
        detections to the detections_output link.
        """

        assert isinstance(detections_input, dai.ImgDetections)

        sequence_num = detections_input.getSequenceNum()
        timestamp = detections_input.getTimestamp()

        detections = detections_input.detections

        configs_group = dai.MessageGroup()
        valid_detections = []
        for detection in detections:
            if detection.confidence > 0.8:
                rect = detection.getBoundingBox()
                rect = self._expand_rect(rect)

                xmin, ymin, xmax, ymax = rect.getOuterRect()
                xmin = int(max(0, xmin * self.w))
                ymin = int(max(0, ymin * self.h))
                xmax = int(min(self.w, xmax * self.w))
                ymax = int(min(self.h, ymax * self.h))

                if xmax - xmin < 50 or ymax - ymin < 12:
                    continue

                valid_detections.append(detection)

                cfg = dai.ImageManipConfig()
                cfg.addCrop(xmin, ymin, xmax - xmin, ymax - ymin)

                if self.target_w is not None and self.target_h is not None:
                    cfg.setOutputSize(self.target_w, self.target_h, self.resize_mode)

                cfg.setTimestamp(timestamp)
                cfg.setSequenceNum(sequence_num)
                configs_group[f"cfg_{len(valid_detections) - 1}"] = cfg

        configs_group.setTimestamp(timestamp)
        configs_group.setSequenceNum(sequence_num)
        self.config_output.send(configs_group)

        valid_msg = dai.ImgDetections()
        valid_msg.setSequenceNum(sequence_num)
        valid_msg.setTimestamp(timestamp)
        valid_msg.detections = valid_detections
        valid_msg.setTransformation(detections_input.getTransformation())

        self.detections_output.send(valid_msg)

    def _validate_positive_integer(self, value: int) -> None:
        if not isinstance(value, int) or value <= 0:
            raise ValueError(f"Expected a positive integer, got {value!r}")

    def _expand_rect(self, rect: dai.RotatedRect) -> dai.RotatedRect:
        s = rect.size

        rect.size = dai.Size2f(s.width * 1.03, s.height * 1.10)

        return rect
