import depthai as dai

from depthai_nodes.message import GatheredData
from depthai_nodes.node.base_host_node import BaseHostNode


class MergeImgDetections(BaseHostNode):
    """Merge all ImgDetections stored in a GatheredData message into one message."""

    def build(self, input: dai.Node.Output) -> "MergeImgDetections":
        self.link_args(input)
        return self

    def process(self, msg: dai.Buffer) -> None:
        if not isinstance(msg, GatheredData):
            raise TypeError(f"Expected GatheredData, got {type(msg)}")

        merged = dai.ImgDetections()
        detections = []
        for item in msg.items:
            if not isinstance(item, dai.ImgDetections):
                raise TypeError(
                    f"Expected GatheredData items to be dai.ImgDetections, got {type(item)}"
                )
            detections.extend(item.detections)

        merged.detections = detections
        merged.setSequenceNum(msg.reference_data.getSequenceNum())
        merged.setTimestamp(msg.reference_data.getTimestamp())
        merged.setTimestampDevice(msg.reference_data.getTimestampDevice())

        if hasattr(msg.reference_data, "getTransformation"):
            transformation = msg.reference_data.getTransformation()
            if transformation is not None:
                merged.setTransformation(transformation)

        self.out.send(merged)
