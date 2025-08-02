import cv2
import depthai as dai
import numpy as np


class BlurBboxes(dai.node.ThreadedHostNode):
    def __init__(self) -> None:
        super().__init__()

        self.rounded_blur = False
        self.input_frame = self.createInput()
        self.input_detections = self.createInput()

        self.out = self.createOutput()

    def run(self) -> None:
        while self.isRunning():
            frame = self.input_frame.get()
            frame_copy = frame.getCvFrame()
            detections = self.input_detections.get().detections

            h, w = frame_copy.shape[:2]
            for detection in detections:
                rect: dai.RotatedRect = detection.rotated_rect
                rect = rect.denormalize(w, h)
                detection = rect.getOuterRect()
                bbox = [int(d) for d in detection]
                bbox[0] = np.clip(bbox[0], 0, w)
                bbox[1] = np.clip(bbox[1], 0, h)
                bbox[2] = np.clip(bbox[2], 0, w)
                bbox[3] = np.clip(bbox[3], 0, h)

                roi = frame_copy[bbox[1] : bbox[3], bbox[0] : bbox[2]]

                roi_width = bbox[2] - bbox[0]
                roi_height = bbox[3] - bbox[1]

                if self.rounded_blur:
                    mask = np.zeros((roi_height, roi_width), np.uint8)
                    polygon = cv2.ellipse2Poly(
                        (int(roi_width / 2), int(roi_height / 2)),
                        (int(roi_width / 2), int(roi_height / 2)),
                        0,
                        0,
                        360,
                        delta=1,
                    )
                    cv2.fillConvexPoly(mask, polygon, 255)
                else:
                    mask = np.full((roi_height, roi_width), 255, np.uint8)

                blurred_roi = cv2.blur(roi, (80, 80))

                blurred_ellipse = cv2.bitwise_and(blurred_roi, blurred_roi, mask=mask)
                inverse_mask = cv2.bitwise_not(mask)
                original_background = cv2.bitwise_and(roi, roi, mask=inverse_mask)
                combined = cv2.add(blurred_ellipse, original_background)

                frame_copy[bbox[1] : bbox[3], bbox[0] : bbox[2]] = combined

            ts = frame.getTimestamp()
            frame_type = frame.getType()
            img = dai.ImgFrame()
            img.setCvFrame(frame_copy, frame_type)
            img.setTimestamp(ts)
            img.setSequenceNum(frame.getSequenceNum())

            self.out.send(img)
