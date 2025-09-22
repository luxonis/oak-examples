import depthai as dai
from typing import Tuple
from depthai_nodes import ImgDetectionsExtended

AVG_MAX_NUM = 10


class CropFace(dai.node.HostNode):
    """A node to create and send a dai.ImageManipConfig crop configuration for the first
    detected face in a list of detections. The default target size is 1920x1080 pixels and can be optionally adjusted.

    To ensure correct synchronization between the crop configurations and the image,
    ensure "inputConfig.setReusePreviousMessage" is set to False in the dai.ImageManip node.

    Attributes
    ----------
    detections_input : dai.Input
        The input link for the ImageDetectionsExtended message.
    config_output : dai.Output
        The output link for the ImageManipConfig messages.
    source_size : Tuple[int, int]
        The size of the source image (width, height).
    target_size : Optional[Tuple[int, int]] = (1920, 1080)
        The size of the target image (width, height).
    resize_mode : dai.ImageManipConfig.ResizeMode = dai.ImageManipConfig.ResizeMode.STRETCH
        The resize mode to use when target size is set. Options are: CENTER_CROP, LETTERBOX, NONE, STRETCH.
    """

    def __init__(self) -> None:
        super().__init__()
        self.config_output = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.ImageManipConfig, True)
            ]
        )

        self.x = []
        self.y = []

    def build(
        self,
        detections_input: dai.Node.Output,
        source_size: Tuple[int, int],
        target_size: Tuple[int, int] = (1920, 1080),
        resize_mode: dai.ImageManipConfig.ResizeMode = dai.ImageManipConfig.ResizeMode.CENTER_CROP,
    ):
        """Link the node input and set the correct source and target image sizes.

        Parameters
        ----------
        detections_input : dai.Node.Output
            The input link for the ImgDetectionsExtended message
        source_size : Tuple[int, int]
            The size of the source image (width, height).
        target_size : Optional[Tuple[int, int]]
            The size of the target image (width, height).
        resize_mode : dai.ImageManipConfig.ResizeMode = dai.ImageManipConfig.ResizeMode.CENTER_CROP
            The resize mode to use when target size is set. Options are: CENTER_CROP, LETTERBOX, NONE, STRETCH.
        """

        self.source_size = source_size
        self.target_size = target_size
        self.resize_mode = resize_mode
        self.link_args(detections_input)

        return self

    def process(self, detection_message: dai.Buffer):
        """Process the input detections and create a crop config. This function is
        ran every time a new ImgDetectionsExtended message is received.

        Sends one crop configuration to the config_output link.
        """
        assert isinstance(detection_message, ImgDetectionsExtended)
        timestamp = detection_message.getTimestamp()
        sequence_num = detection_message.getSequenceNum()

        dets = detection_message.detections
        # Skip the current frame / load new frame
        cfg = dai.ImageManipConfig()
        cfg.setSkipCurrentImage(True)
        cfg.setTimestamp(timestamp)
        cfg.setSequenceNum(sequence_num)

        if len(dets) > 0:
            cfg.setSkipCurrentImage(False)
            coords = dets[0]
            rect = coords.rotated_rect

            x = rect.center.x
            y = rect.center.y
            x_avg, y_avg = self._average_filter(x, y)
            crop_w = self.target_size[0] / self.source_size[0]
            crop_h = self.target_size[1] / self.source_size[1]

            crop_rectangle = dai.RotatedRect(
                dai.Point2f(x_avg, y_avg), dai.Size2f(crop_w, crop_h), 0
            )

            cfg.addCropRotatedRect(crop_rectangle, normalizedCoords=True)
            cfg.setOutputSize(
                self.target_size[0], self.target_size[1], self.resize_mode
            )
            cfg.setReusePreviousImage(False)
            cfg.setFrameType(dai.ImgFrame.Type.NV12)

        self.config_output.send(cfg)

    def _average_filter(self, x, y) -> Tuple[int, int]:
        """
        Apply a simple average filter to the x and y coordinates to smooth out the crop center position over multiple frames.
        """

        self.x.append(x)
        self.y.append(y)

        if AVG_MAX_NUM < len(self.x):
            self.x.pop(0)
        if AVG_MAX_NUM < len(self.y):
            self.y.pop(0)

        x_avg = sum(self.x) / len(self.x)
        y_avg = sum(self.y) / len(self.y)

        return x_avg, y_avg
