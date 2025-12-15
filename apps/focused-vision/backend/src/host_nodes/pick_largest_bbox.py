import depthai as dai

from depthai_nodes import ImgDetectionsExtended
from depthai_nodes.node import BaseHostNode


class PickLargestBbox(BaseHostNode):
    """"""

    def build(self, nn_output: dai.Node.Output) -> "PickLargestBbox":
        self.link_args(nn_output)
        # self.sendProcessingToPipeline(False)
        return self

    def process(self, nn_output: dai.Buffer) -> None:
        assert isinstance(nn_output, ImgDetectionsExtended)
        max_area = -1_000
        largest_bbox = None
        for detection in nn_output.detections:
            area = (
                detection.rotated_rect.size.width * detection.rotated_rect.size.height
            )
            if area > max_area:
                max_area = area
                largest_bbox = detection
        for detection in nn_output.detections.copy():
            if detection is not largest_bbox:
                nn_output.detections.remove(detection)
        self.out.send(nn_output)
