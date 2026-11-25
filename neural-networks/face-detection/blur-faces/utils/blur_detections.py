import cv2
import depthai as dai
import numpy as np


class BlurBboxes(dai.node.HostNode):
    def __init__(self) -> None:
        super().__init__()
        self.rounded_blur = False

    def build(
        self, frame: dai.Node.Output, detections: dai.Node.Output
    ) -> "BlurBboxes":
        # HostNode pairs each frame with the detections from the same capture.
        self.link_args(frame, detections)
        return self

    def process(self, frame: dai.Buffer, detections: dai.Buffer) -> None:
        assert isinstance(frame, dai.ImgFrame)
        frame_copy = frame.getCvFrame()

        h, w = frame_copy.shape[:2]
        for detection in detections.detections:
            rect: dai.RotatedRect = detection.getBoundingBox()
            rect = rect.denormalize(w, h)
            detection = rect.getOuterRect()
            bbox = [int(d) for d in detection]
            bbox[0] = np.clip(bbox[0], 0, w)
            bbox[1] = np.clip(bbox[1], 0, h)
            bbox[2] = np.clip(bbox[2], 0, w)
            bbox[3] = np.clip(bbox[3], 0, h)
            if bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
                continue  # box lies outside the frame after clipping

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

        img = dai.ImgFrame()
        img.setCvFrame(frame_copy, frame.getType())
        # Blurring keeps the pixel grid, so keep the source timing and geometry.
        img.setBufferMetadataFrom(frame)
        img.setTransformation(frame.getTransformation())

        self.out.send(img)
