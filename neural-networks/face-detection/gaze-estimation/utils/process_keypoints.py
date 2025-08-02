import depthai as dai
from depthai_nodes import ImgDetectionExtended, ImgDetectionsExtended


class LandmarksProcessing(dai.node.ThreadedHostNode):
    def __init__(self):
        super().__init__()
        self.detections_input = self.createInput()
        self.left_config_output = self.createOutput()
        self.right_config_output = self.createOutput()
        self.face_config_output = self.createOutput()

        self._w = 1
        self._h = 1

        self._target_w = 100
        self._target_h = 100

    def run(self) -> None:
        while self.isRunning():
            img_detections = self.detections_input.get()
            detections = img_detections.detections
            sequence_num = img_detections.getSequenceNum()
            timestamp = img_detections.getTimestamp()

            left_configs_message = dai.MessageGroup()
            right_configs_message = dai.MessageGroup()
            face_configs_message = dai.MessageGroup()
            for i, detection in enumerate(detections):
                detection: ImgDetectionExtended = detection
                keypoints = detection.keypoints
                face_size = detection.rotated_rect.size
                face_w, face_h = face_size.width * self.w, face_size.height * self.h

                right_eye = self.crop_rectangle(
                    keypoints[0], face_w * 0.25, face_h * 0.25
                )
                right_configs_message[str(i + 100)] = self.create_crop_cfg(
                    right_eye, img_detections
                )

                left_eye = self.crop_rectangle(
                    keypoints[1], face_w * 0.25, face_h * 0.25
                )
                left_configs_message[str(i + 100)] = self.create_crop_cfg(
                    left_eye, img_detections
                )

                face_rect = detection.rotated_rect
                face_rect = face_rect.denormalize(self.w, self.h)
                face_configs_message[str(i + 100)] = self.create_crop_cfg(
                    face_rect, img_detections
                )

            left_configs_message.setSequenceNum(sequence_num)
            left_configs_message.setTimestamp(timestamp)

            right_configs_message.setSequenceNum(sequence_num)
            right_configs_message.setTimestamp(timestamp)

            face_configs_message.setSequenceNum(sequence_num)
            face_configs_message.setTimestamp(timestamp)

            self.face_config_output.send(face_configs_message)
            self.left_config_output.send(left_configs_message)
            self.right_config_output.send(right_configs_message)

    def crop_rectangle(self, center_keypoint: dai.Point2f, crop_w: int, crop_h: int):
        center = [
            int(center_keypoint.x * self.w),
            int(center_keypoint.y * self.h),
        ]
        center_keypoint = dai.Point2f(center[0], center[1])
        size = dai.Size2f(crop_w, crop_h)
        croped_rectangle = dai.RotatedRect(center_keypoint, size, 0)

        return croped_rectangle.denormalize(self.w, self.h)

    def create_crop_cfg(
        self, rectangle: dai.RotatedRect, img_detections: ImgDetectionsExtended
    ):
        cfg = dai.ImageManipConfig()
        cfg.addCropRotatedRect(rectangle, normalizedCoords=False)
        cfg.setOutputSize(self.target_w, self.target_h)
        cfg.setReusePreviousImage(False)
        cfg.setTimestamp(img_detections.getTimestamp())
        cfg.setSequenceNum(img_detections.getSequenceNum())

        return cfg

    def set_target_size(self, w: int, h: int):
        """Set the target size for the output image."""
        self._target_w = w
        self._target_h = h

    def set_source_size(self, w: int, h: int):
        """Set the source size for the input image."""
        self._w = w
        self._h = h

    @property
    def w(self):
        return self._w

    @property
    def h(self):
        return self._h

    @property
    def target_w(self):
        return self._target_w

    @property
    def target_h(self):
        return self._target_h

    @w.setter
    def w(self, w):
        self._w = w

    @h.setter
    def h(self, h):
        self._h = h

    @target_w.setter
    def target_w(self, target_w):
        self._target_w = target_w

    @target_h.setter
    def target_h(self, target_h):
        self._target_h = target_h
