import depthai as dai
import numpy as np
import cv2
from typing import Sequence


class DisparityToDetections(dai.node.HostNode):
    """
    Extracts object bounding boxes from disparity maps.

    Args:
        disparity (dai.Node.Output): Input disparity map.
        max_disparity (float): Maximum disparity value used for normalization or filtering.
        roi (Tuple[int, int, int, int]): Region of interest defined as (xmin, ymin, xmax, ymax).
            Bounding boxes will only be extracted within this area. By default, the whole frame is used.
        area_threshold (int): Minimum area of bounding boxes to be extracted.
            This is arbitrary and can be changed to suit the application. By default, bounding boxes with area larger than 5000 pixels are extracted.

    Returns:
        dai.ImgDetections: Detected bounding boxes.
    """

    def __init__(self):
        super().__init__()

    def build(
        self,
        disparity: dai.Node.Output,
        max_disparity: float,
        roi: tuple = None,
        area_threshold: int = 5000,
    ) -> "DisparityToDetections":
        self.max_disparity = max_disparity
        self.roi = roi
        self.area_threshold = area_threshold
        self.link_args(disparity)
        return self

    def process(self, disparity_msg: dai.Buffer):
        assert isinstance(disparity_msg, dai.ImgFrame)
        disparity_frame = disparity_msg.getCvFrame()
        disparity_frame = disparity_frame * (255 / self.max_disparity)
        disparity_frame = disparity_frame.astype(np.uint8)

        contours = self.get_contours(disparity_frame)
        dets_msg = self.get_detections(contours, disparity_frame)
        dets_msg.setTimestamp(disparity_msg.getTimestamp())
        dets_msg.setSequenceNum(disparity_msg.getSequenceNum())
        dets_msg.setTimestampDevice(disparity_msg.getTimestampDevice())
        dets_msg.setTransformation(disparity_msg.getTransformation())
        self.out.send(dets_msg)

    def get_detections(self, contours, disparity_frame) -> dai.ImgDetections:
        dets = dai.ImgDetections()
        if len(contours) != 0:
            c = max(contours, key=cv2.contourArea)
            xmin, ymin, w, h = cv2.boundingRect(c)
            if self.roi is not None:
                xmin += self.roi[0]
                ymin += self.roi[1]
            area = w * h

            if area > self.area_threshold:
                det = dai.ImgDetection()
                det.label = 0
                det.confidence = 1.0
                frame_height, frame_width = disparity_frame.shape
                det.xmin = xmin / frame_width
                det.ymin = ymin / frame_height
                det.xmax = (xmin + w) / frame_width
                det.ymax = (ymin + h) / frame_height
                dets.detections = [det]

        return dets

    def get_contours(self, disparity_frame) -> Sequence[np.ndarray]:
        if self.roi is not None:
            xmin, ymin, xmax, ymax = self.roi
            disparity_frame = disparity_frame[ymin:ymax, xmin:xmax]
        _, thresh = cv2.threshold(disparity_frame, 125, 145, cv2.THRESH_BINARY)
        blob = cv2.morphologyEx(
            thresh,
            cv2.MORPH_OPEN,
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (37, 37)),
        )
        edged = cv2.Canny(blob, 20, 80)
        contours, _ = cv2.findContours(edged, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

        return contours
