import depthai as dai


class BarcodeRegions(dai.node.HostNode):
    """Keep proportional barcode ROI expansion and rotation for FrameCropper."""

    def build(self, detections: dai.Node.Output) -> "BarcodeRegions":
        self.link_args(detections)
        return self

    def process(self, detections: dai.ImgDetections) -> dai.ImgDetections:
        expanded = []
        for detection in detections.detections:
            rect = detection.getBoundingBox()
            region = dai.ImgDetection()
            region.label = detection.label
            region.confidence = detection.confidence
            region.setBoundingBox(
                dai.RotatedRect(
                    rect.center,
                    dai.Size2f(rect.size.width * 1.15, rect.size.height * 1.15, True),
                    rect.angle,
                )
            )
            expanded.append(region)

        regions = dai.ImgDetections()
        regions.detections = expanded
        regions.setTransformation(detections.getTransformation())
        regions.setTimestamp(detections.getTimestamp())
        regions.setTimestampDevice(detections.getTimestampDevice())
        regions.setSequenceNum(detections.getSequenceNum())
        return regions
