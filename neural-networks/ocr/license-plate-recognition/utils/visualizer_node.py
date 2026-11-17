import cv2
import depthai as dai
import numpy as np

from depthai_nodes import GatheredData


class VisualizeLicensePlates(dai.node.HostNode):
    def build(
        self, frames: dai.Node.Output, results: dai.Node.Output
    ) -> "VisualizeLicensePlates":
        self.link_args(frames, results)
        return self

    def process(self, frame_message: dai.ImgFrame, results: dai.Buffer) -> None:
        assert isinstance(results, GatheredData)
        if frame_message.getSequenceNum() != results.getSequenceNum():
            return
        frame = frame_message.getCvFrame()
        frame_h, frame_w = frame.shape[:2]
        # Each item matches a selected region and its explicit (vehicle, plate) index.
        for lp_detection, result in zip(
            results.reference_data.detections, results.items
        ):
            text = "".join(result["ocr"].classes)
            license_plate = result["crop"].getCvFrame()

            if len(text) < 5:
                continue

            lp_x_min = int(lp_detection.xmin * frame_w)
            lp_y_min = int(lp_detection.ymin * frame_h)
            lp_x_max = int(lp_detection.xmax * frame_w)
            lp_y_max = int(lp_detection.ymax * frame_h)

            lp_x_min = np.clip(lp_x_min, 0, frame_w)
            lp_y_min = np.clip(lp_y_min, 0, frame_h)
            lp_x_max = np.clip(lp_x_max, 0, frame_w)
            lp_y_max = np.clip(lp_y_max, 0, frame_h)

            if lp_x_max <= lp_x_min or lp_y_max <= lp_y_min:
                continue

            cv2.rectangle(
                frame, (lp_x_min, lp_y_min), (lp_x_max, lp_y_max), (0, 255, 0), 2
            )
            preview_w, preview_h = min(160, frame_w), min(48, frame_h)
            crop_h = preview_h // 2
            plate_preview = cv2.resize(license_plate, (preview_w, crop_h))
            label = np.full((preview_h - crop_h, preview_w, 3), 255, dtype=np.uint8)
            font = cv2.FONT_HERSHEY_SIMPLEX
            text_width = cv2.getTextSize(text, font, 0.6, 1)[0][0]
            font_scale = 0.6 * min(1.0, (preview_w - 4) / max(1, text_width))
            cv2.putText(
                label,
                text,
                (2, max(12, label.shape[0] - 5)),
                font,
                font_scale,
                (0, 0, 255),
                1,
                cv2.LINE_AA,
            )
            preview = np.concatenate((plate_preview, label), axis=0)
            preview_x = int(np.clip(lp_x_min, 0, frame_w - preview_w))
            below_y = lp_y_max + 3
            preview_y = (
                below_y
                if below_y + preview_h <= frame_h
                else max(0, lp_y_min - preview_h - 3)
            )
            frame[
                preview_y : preview_y + preview_h, preview_x : preview_x + preview_w
            ] = preview

        img = dai.ImgFrame()
        img.setCvFrame(frame, frame_message.getType())
        img.setTimestamp(frame_message.getTimestamp())
        img.setTimestampDevice(frame_message.getTimestampDevice())
        img.setSequenceNum(frame_message.getSequenceNum())
        img.setTransformation(frame_message.getTransformation())
        self.out.send(img)
