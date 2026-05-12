from typing import Optional, Tuple
import time

import depthai as dai


class CropConfigsCreator(dai.node.HostNode):
    """A node to create and send a dai.ImageManipConfigV2 crop configuration for each
    detection in a list of detections. An optional target size and resize mode can be
    set to ensure uniform crop sizes.

    To ensure correct synchronization between the crop configurations and the image,
    ensure "inputConfig.setReusePreviousMessage" is set to False in the dai.ImageManipV2 node.

    Attributes
    ----------
    detections_input : dai.Input
        The input link for the dai.ImgDetections message.
    config_output : dai.Output
        The output link for the ImageManipConfigV2 messages.
    detections_output : dai.Output
        The output link for the dai.ImgDetections message.
    source_size : Tuple[int, int]
        The size of the source image (width, height).
    target_size : Optional[Tuple[int, int]] = None
        The size of the target image (width, height). If None, crop sizes will not be uniform.
    resize_mode : dai.ImageManipConfigV2.ResizeMode = dai.ImageManipConfigV2.ResizeMode.STRETCH
        The resize mode to use when target size is set. Options are: CENTER_CROP, LETTERBOX, NONE, STRETCH.
    """

    def __init__(self) -> None:
        """Initializes the node."""
        super().__init__()
        self.config_output = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.ImageManipConfig, True)
            ]
        )

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
        """Returns the width of the source image.

        @return: Width of the source image.
        @rtype: int
        """
        return self._w

    @property
    def h(self) -> int:
        """Returns the height of the source image.

        @return: Height of the source image.
        @rtype: int
        """
        return self._h

    @property
    def target_w(self) -> int:
        """Returns the width of the target image.

        @return: Width of the target image.
        @rtype: int
        """
        return self._target_w

    @property
    def target_h(self) -> int:
        """Returns the height of the target image.

        @return: Height of the target image.
        @rtype: int
        """
        return self._target_h

    @w.setter
    def w(self, w: int):
        """Sets the width of the source image.

        @param w: Width of the source image.
        @type w: int
        @raise TypeError: If w is not an integer.
        @raise ValueError: If w is less than 1.
        """
        self._validate_positive_integer(w)
        self._w = w

    @h.setter
    def h(self, h: int):
        """Sets the height of the source image.

        @param h: Height of the source image.
        @type h: int
        @raise TypeError: If h is not an integer.
        @raise ValueError: If h is less than 1.
        """
        self._validate_positive_integer(h)
        self._h = h

    @target_w.setter
    def target_w(self, target_w: int):
        """Sets the width of the target image.

        @param target_w: Width of the target image.
        @type target_w: int
        @raise TypeError: If target_w is not an integer.
        @raise ValueError: If target_w is less than 1.
        """
        self._validate_positive_integer(target_w)
        self._target_w = target_w

    @target_h.setter
    def target_h(self, target_h: int):
        """Sets the height of the target image.

        @param target_h: Height of the target image.
        @type target_h: int
        @raise TypeError: If target_h is not an integer.
        @raise ValueError: If target_h is less than 1.
        """
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
        resize_mode : dai.ImageManipConfigV2.ResizeMode = dai.ImageManipConfigV2.ResizeMode.STRETCH
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
        ran every time a new dai.ImgDetections message is received.

        Sends len(detections) number of crop configurations to the config_output link.
        In addition sends a dai.ImgDetections object containing the corresponding
        detections to the detections_output link.
        """

        assert isinstance(detections_input, dai.ImgDetections)
        sequence_num = detections_input.getSequenceNum()
        timestamp = detections_input.getTimestamp()

        detections = detections_input.detections

        # Skip the current frame / load new frame
        cfg = dai.ImageManipConfig()
        cfg.setSkipCurrentImage(True)
        cfg.setTimestamp(timestamp)
        cfg.setSequenceNum(sequence_num)
        send_status = False
        attempts = 0
        while (
            not send_status and attempts < 100
        ):  # Limit attempts to prevent infinite loop
            send_status = self.config_output.trySend(cfg)
            if not send_status:
                attempts += 1
                time.sleep(0.001)  # Small delay to prevent busy waiting

        for i in range(len(detections)):
            cfg = dai.ImageManipConfig()
            detection: dai.ImgDetection = detections[i]

            x_center = (detection.xmin + detection.xmax) / 2
            y_center = (detection.ymin + detection.ymax) / 2
            width = (detection.xmax - detection.xmin) * 1.15
            height = (detection.ymax - detection.ymin) * 1.15
            rect = dai.RotatedRect(
                dai.Point2f(x_center, y_center), dai.Size2f(width, height), 0.0
            )

            cfg.addCropRotatedRect(rect, normalizedCoords=True)

            if self.target_w is not None and self.target_h is not None:
                cfg.setOutputSize(self.target_w, self.target_h, self.resize_mode)

            cfg.setReusePreviousImage(True)
            cfg.setTimestamp(timestamp)
            cfg.setSequenceNum(sequence_num)

            send_status = False
            attempts = 0
            while (
                not send_status and attempts < 100
            ):  # Limit attempts to prevent infinite loop
                send_status = self.config_output.trySend(cfg)
                if not send_status:
                    attempts += 1
                    time.sleep(0.001)  # Small delay to prevent busy waiting

        self.detections_output.send(detections_input)

    def _validate_positive_integer(self, value: int):
        """Validates that the set size is a positive integer.

        @param value: The value to validate.
        @type value: int
        @raise TypeError: If value is not an integer.
        @raise ValueError: If value is less than 1.
        """
        if not isinstance(value, int):
            raise TypeError("Value must be an integer.")
        if value < 1:
            raise ValueError("Value must be greater than 1.")
