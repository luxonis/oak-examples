import cv2
import depthai as dai
import numpy as np


class VisualizeLicensePlates(dai.node.ThreadedHostNode):
    def __init__(self) -> None:
        super().__init__()

        self.vehicle_detections = self.createInput()
        self.input_frame = self.createInput()
        self.ocr_results = self.createInput()
        self.lp_crop_detections = self.createInput()
        self.lp_crop_images = self.createInput()

        self.out = self.createOutput()

    def run(self) -> None:
        while self.isRunning():
            frame_message = self.input_frame.get()
            frame = frame_message.getCvFrame()
            frame_h, frame_w = frame.shape[:2]

            detections = self.vehicle_detections.get().detections
            crop_detections = self.lp_crop_detections.get().detections

            for detection, lp_detection in zip(detections, crop_detections):
                x_min = int(detection.xmin * frame_w)
                y_min = int(detection.ymin * frame_h)
                x_max = int(detection.xmax * frame_w)
                y_max = int(detection.ymax * frame_h)

                vehicle_w = x_max - x_min
                vehicle_h = y_max - y_min

                ocr_message = self.ocr_results.get()
                text = "".join(ocr_message.classes)
                license_plate = self.lp_crop_images.get().getCvFrame()

                if len(text) < 5:
                    continue

                lp_x_min = int(lp_detection.xmin * vehicle_w) + x_min
                lp_y_min = int(lp_detection.ymin * vehicle_h) + y_min
                lp_x_max = int(lp_detection.xmax * vehicle_w) + x_min
                lp_y_max = int(lp_detection.ymax * vehicle_h) + y_min

                lp_x_min = np.clip(lp_x_min, 0, frame_w)
                lp_y_min = np.clip(lp_y_min, 0, frame_h)
                lp_x_max = np.clip(lp_x_max, 0, frame_w)
                lp_y_max = np.clip(lp_y_max, 0, frame_h)

                license_plate = cv2.resize(license_plate, (80, 12))

                white_frame = np.ones((12, 80, 3)) * 255
                cv2.putText(
                    white_frame,
                    text,
                    (2, 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.4,
                    (0, 0, 255),
                    1,
                )
                crop_region = frame[lp_y_max : lp_y_max + 24, lp_x_min : lp_x_min + 80]
                lp_text = np.concatenate((license_plate, white_frame), axis=0)
                lp_text = cv2.resize(
                    lp_text, (crop_region.shape[1], crop_region.shape[0])
                )

                frame[
                    lp_y_max : lp_y_max + crop_region.shape[0],
                    lp_x_min : lp_x_min + crop_region.shape[1],
                ] = lp_text

            ts = frame_message.getTimestamp()
            frame_type = frame_message.getType()
            img = dai.ImgFrame()
            img.setCvFrame(frame, frame_type)
            img.setTimestamp(ts)
            img.setTimestampDevice(frame_message.getTimestampDevice())
            self.out.send(img)
