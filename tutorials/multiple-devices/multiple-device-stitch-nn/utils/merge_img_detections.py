import depthai as dai
from depthai_nodes.message import GatheredData
from depthai_nodes.node.base_host_node import BaseHostNode


class MergeImgDetections(BaseHostNode):
    """Transform each tile to its matched reference frame, then merge detections."""

    def build(self, input: dai.Node.Output) -> "MergeImgDetections":
        self.link_args(input)
        return self

    def process(self, msg: dai.Buffer) -> None:
        if not isinstance(msg, GatheredData):
            raise TypeError(f"Expected GatheredData, got {type(msg)}")

        merged = dai.ImgDetections()
        detections = []
        transformation = msg.reference_data.getTransformation()
        for item in msg.items:
            if not isinstance(item, dai.ImgDetections):
                raise TypeError(
                    f"Expected GatheredData items to be dai.ImgDetections, got {type(item)}"
                )
            if item.getTransformation() is None or transformation is None:
                raise RuntimeError(
                    "Detection mapping requires source and reference transformations"
                )
            detections.extend(item.transformTo(transformation).detections)

        merged.detections = detections
        merged.setBufferMetadataFrom(msg.reference_data)
        merged.setTransformation(transformation)

        self.out.send(merged)
