import depthai as dai
from depthai_nodes.message.utils import copy_message


class Switch(dai.node.HostNode):
    """"""

    def __init__(self):
        super().__init__()
        self.has_detections = self.createOutput()
        self.no_detections = self.createOutput()
        self.rgb = self.createOutput()

    def build(self, node_out: dai.Node.Output, rgb_out: dai.Node.Output) -> "Router":
        self.link_args(node_out, rgb_out)
        self.sendProcessingToPipeline(True)
        return self

    def process(self, detections: dai.Buffer, rgb: dai.ImgFrame) -> None:
        assert isinstance(detections, dai.ImgDetections)
        detections: dai.ImgDetections
        if detections.detections:
            # Match the original display cropper's axis-aligned regions.
            detections = copy_message(detections)
            regions = detections.detections
            for region in regions:
                xmin, ymin, xmax, ymax = region.getOuterBoundingBox()
                rect = dai.Rect(xmin, ymin, xmax - xmin, ymax - ymin, True)
                region.setBoundingBox(dai.RotatedRect(rect))
            detections.detections = regions
            self.has_detections.send(detections)
            self.rgb.send(rgb)
        else:
            self.no_detections.send(detections)
