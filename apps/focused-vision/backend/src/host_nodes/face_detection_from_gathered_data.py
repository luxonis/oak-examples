import depthai as dai

from depthai_nodes.message import Collection, GatheredData


class FaceDetectionFromCollection(dai.node.HostNode):
    """"""

    def build(self, node_out: dai.Node.Output) -> "FaceDetectionFromCollection":
        self.link_args(node_out)
        self.sendProcessingToPipeline(True)
        return self

    def process(self, collected_messages: dai.Buffer) -> dai.ImgDetections:
        assert isinstance(collected_messages, (Collection, GatheredData))
        if isinstance(collected_messages, GatheredData):
            reference = collected_messages.reference_data
            collected = collected_messages.items
        else:
            reference = collected_messages
            collected = collected_messages.items
        if collected:
            detections = collected[0]
        else:
            detections = dai.ImgDetections()
            detections.setTimestamp(reference.getTimestamp())
            detections.setTimestampDevice(reference.getTimestampDevice())
            detections.setSequenceNum(reference.getSequenceNum())
        return detections
