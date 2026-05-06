import depthai as dai

from depthai_nodes.message import Collection, GatheredData
from depthai_nodes.node import BaseHostNode


class MergeImgDetections(BaseHostNode):
    def build(self, collection_out: dai.Node.Output) -> "MergeImgDetections":
        self.link_args(collection_out)
        return self

    def process(self, collection: dai.Buffer) -> None:
        assert isinstance(collection, (Collection, GatheredData))
        img_detections: dai.ImgDetections = dai.ImgDetections()
        if isinstance(collection, GatheredData):
            reference = collection.reference_data
        else:
            reference = collection
        img_detections.setTimestamp(reference.getTimestamp())
        img_detections.setTimestampDevice(reference.getTimestampDevice())
        img_detections.setSequenceNum(reference.getSequenceNum())
        detections = []
        for img_dets in collection.items:
            img_dets: dai.ImgDetections
            detections.extend(img_dets.detections)
        img_detections.detections = detections
        if hasattr(reference, "getTransformation"):
            transformation = reference.getTransformation()
            if transformation is not None:
                img_detections.setTransformation(transformation)
        self.out.send(img_detections)
