import depthai as dai

from depthai_nodes.message import Collection
from depthai_nodes.node.base_host_node import BaseHostNode


class MergeImgDetections(BaseHostNode):
    """Merge all ImgDetections stored in a Collection message into one message."""

    def build(self, input: dai.Node.Output) -> "MergeImgDetections":
        self.link_args(input)
        return self

    def process(self, msg: dai.Buffer) -> None:
        if not isinstance(msg, Collection):
            raise TypeError(f"Expected Collection, got {type(msg)}")

        merged = dai.ImgDetections()
        detections = []
        for item in msg.items:
            if not isinstance(item, dai.ImgDetections):
                raise TypeError(
                    f"Expected Collection items to be dai.ImgDetections, got {type(item)}"
                )
            detections.extend(item.detections)

        merged.detections = detections
        merged.setSequenceNum(msg.getSequenceNum())
        merged.setTimestamp(msg.getTimestamp())
        merged.setTimestampDevice(msg.getTimestampDevice())

        if hasattr(msg, "getTransformation"):
            transformation = msg.getTransformation()
            if transformation is not None:
                merged.setTransformation(transformation)

        self.out.send(merged)
