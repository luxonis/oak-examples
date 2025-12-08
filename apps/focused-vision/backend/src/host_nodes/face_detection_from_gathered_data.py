import depthai as dai

from depthai_nodes.message import GatheredData, ImgDetectionsExtended


class FaceDetectionFromGatheredData(dai.node.HostNode):
    """"""

    def build(self, node_out: dai.Node.Output) -> "HeadDetectionFromGatheredData":
        self.link_args(node_out)
        self.sendProcessingToPipeline(True)
        return self

    def process(self, gathered_data: dai.Buffer) -> ImgDetectionsExtended:
        assert isinstance(gathered_data, GatheredData)
        gathered_data: GatheredData
        gathered: list[ImgDetectionsExtended] = gathered_data.gathered
        if gathered:
            detections = gathered[0]
        else:
            detections = ImgDetectionsExtended()
            detections.setTimestamp(gathered_data.getTimestamp())
            detections.setTimestampDevice(gathered_data.getTimestampDevice())
            detections.setSequenceNum(gathered_data.getSequenceNum())
        return detections
