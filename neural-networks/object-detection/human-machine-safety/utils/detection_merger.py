import depthai as dai


class DetectionMerger(dai.node.HostNode):
    """Merges multiple detection messages into a single one."""

    def __init__(self):
        super().__init__()
        self._detection_1_label_offset = 0
        self._detection_2_label_offset = 0
        self.output = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.Buffer, True)
            ]
        )

    def build(self, det_nn_1: dai.Node.Output, det_nn_2: dai.Node.Output):
        self.link_args(det_nn_1, det_nn_2)
        return self

    def process(self, det_nn_1: dai.Buffer, det_nn_2: dai.Buffer) -> dai.ImgDetections:
        assert isinstance(
            det_nn_1,
            (dai.ImgDetections, dai.SpatialImgDetections),
        )
        assert type(det_nn_1) is type(det_nn_2)
        new_dets = type(det_nn_1)()
        new_dets_list = det_nn_1.detections + det_nn_2.detections
        for ind, d in enumerate(new_dets_list):
            if ind < len(det_nn_1.detections):
                d.label += self._detection_1_label_offset
            else:
                d.label += self._detection_2_label_offset

        new_dets.detections = det_nn_1.detections + det_nn_2.detections
        new_dets.setSequenceNum(det_nn_1.getSequenceNum())
        new_dets.setTimestamp(det_nn_1.getTimestamp())
        new_dets.setTransformation(det_nn_1.getTransformation())
        self.output.send(new_dets)

    def set_detection_1_label_offset(self, offset: int):
        """This number is added to all labels of the first detection message (`det_nn_1` input)."""
        self._detection_1_label_offset = offset

    def set_detection_2_label_offset(self, offset: int):
        """This number is added to all labels of the second detection message (`det_nn_2` input)."""
        self._detection_2_label_offset = offset
