import depthai as dai
from depthai_nodes import ImgDetectionsExtended, ImgDetectionExtended
import cv2


class AnnotationNode(dai.node.HostNode):
    """Transforms ImgDetectionsExtended received from parsers to dai.ImgDetections"""

    def __init__(self) -> None:
        super().__init__()

        self.out_detections = self.createOutput()
        self.out_depth = self.createOutput()

    def build(
        self,
        detections: dai.Node.Output,
        video: dai.Node.Output,
        depth: dai.Node.Output,
    ) -> "AnnotationNode":
        self.link_args(detections, video, depth)
        return self

    def process(
        self,
        detections_msg: dai.Buffer,
        video_msg: dai.ImgFrame,
        depth_msg: dai.ImgFrame,
    ):
        assert isinstance(detections_msg, dai.SpatialImgDetections)
        img_detections = ImgDetectionsExtended()
        for detection in detections_msg.detections:
            detection: dai.SpatialImgDetection = detection
            img_detection = ImgDetectionExtended()
            img_detection.label = detection.label
            rotated_rect = (
                (detection.xmax + detection.xmin) / 2,
                (detection.ymax + detection.ymin) / 2,
                detection.xmax - detection.xmin,
                detection.ymax - detection.ymin,
                0,
            )
            img_detection.rotated_rect = rotated_rect
            img_detection.confidence = detection.confidence
            img_detections.detections.append(img_detection)

        depth_map = depth_msg.getFrame()
        colorred_depth_map = cv2.applyColorMap(
            cv2.convertScaleAbs(depth_map, alpha=0.3), cv2.COLORMAP_JET
        )

        depth_frame = dai.ImgFrame()
        depth_frame.setCvFrame(colorred_depth_map, dai.ImgFrame.Type.BGR888i)
        depth_frame.setTimestamp(depth_msg.getTimestamp())
        depth_frame.setSequenceNum(depth_msg.getSequenceNum())

        img_detections.setTimestamp(detections_msg.getTimestamp())
        img_detections.setSequenceNum(detections_msg.getSequenceNum())
        img_detections.setTransformation(video_msg.getTransformation())

        self.out_detections.send(img_detections)
        self.out_depth.send(depth_frame)
