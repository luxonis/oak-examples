import depthai as dai
from depthai_nodes import ImgDetectionsExtended, ImgDetectionExtended
from typing import Tuple


class ProcessDetections(dai.node.HostNode):
    """A host node for processing a list of detections in a two-stage pipeline.
    The node iterates over a list of detections and sends a dai.MessageGroup with
    a list of ImageManipConfig objects that can be executed by the ImageManip node.

    Before use, the target size need to be set with the set_target_size method.
    Attributes
    ----------
    detections_input : dai.Input
        The input message for the detections.
    config_output : dai.Output
        The output message for the ImageManipConfig objects.
    num_configs_output : dai.Output
        The output message for the number of configs.
    padding: float
        The padding factor to enlarge the bounding box a little bit.

    """

    def __init__(self):
        super().__init__()
        self.detections_input = self.createInput()
        self.config_output = self.createOutput()
        self.num_configs_output = self.createOutput()
        self.padding = 0.1
        self._target_h = None
        self._target_w = None

    def build(
        self,
        detections_input: dai.Node.Output,
        padding: float,
        target_size: Tuple[int, int],
    ) -> "ProcessDetections":
        self.padding = padding
        self._target_w = target_size[0]
        self._target_h = target_size[1]
        self.link_args(detections_input)
        return self

    def process(self, img_detections: dai.Buffer) -> None:
        assert isinstance(img_detections, ImgDetectionsExtended)
        detections = img_detections.detections

        num_detections = len(detections)
        num_cfgs_message = dai.Buffer(num_detections)

        num_cfgs_message.setTimestamp(img_detections.getTimestamp())
        num_cfgs_message.setSequenceNum(img_detections.getSequenceNum())
        self.num_configs_output.send(num_cfgs_message)

        for i, detection in enumerate(detections):
            cfg = dai.ImageManipConfig()
            detection: ImgDetectionExtended = detection
            rect = detection.rotated_rect

            new_rect = dai.RotatedRect()
            new_rect.center.x = rect.center.x
            new_rect.center.y = rect.center.y
            new_rect.size.width = rect.size.width + 0.1 * 2
            new_rect.size.height = rect.size.height + 0.1 * 2
            new_rect.angle = 0

            cfg.addCropRotatedRect(new_rect, normalizedCoords=True)
            cfg.setOutputSize(
                self._target_w,
                self._target_h,
                dai.ImageManipConfig.ResizeMode.STRETCH,
            )
            cfg.setReusePreviousImage(False)
            cfg.setTimestamp(img_detections.getTimestamp())
            cfg.setSequenceNum(img_detections.getSequenceNum())
            self.config_output.send(cfg)
