import depthai as dai


class LandmarksProcessing(dai.node.HostNode):
    def __init__(self):
        super().__init__()
        self.inputs["source"].getParent().setTimestampSource(
            dai.node.Sync.TimestampSource.DEVICE
        )
        self.left_config_output = self.createOutput()
        self.right_config_output = self.createOutput()
        self.face_config_output = self.createOutput()

        self.w, self.h = 1, 1
        self.target_w, self.target_h = 100, 100

    def process(self, img_detections: dai.ImgDetections, source: dai.ImgFrame) -> None:
        img_detections = img_detections.transformTo(source.getTransformation())
        self.w, self.h = source.getWidth(), source.getHeight()
        detections = img_detections.detections

        left_configs_message = dai.MessageGroup()
        right_configs_message = dai.MessageGroup()
        face_configs_message = dai.MessageGroup()
        for i, detection in enumerate(detections):
            detection: dai.ImgDetection = detection
            keypoints = detection.getKeypoints2f()
            face_size = detection.getBoundingBox().size
            face_w, face_h = face_size.width * self.w, face_size.height * self.h

            right_eye = self.crop_rectangle(keypoints[0], face_w * 0.25, face_h * 0.25)
            right_configs_message[f"cfg_{i}"] = self.create_crop_cfg(
                right_eye, img_detections
            )

            left_eye = self.crop_rectangle(keypoints[1], face_w * 0.25, face_h * 0.25)
            left_configs_message[f"cfg_{i}"] = self.create_crop_cfg(
                left_eye, img_detections
            )

            face_rect = detection.getBoundingBox()
            face_rect = face_rect.denormalize(self.w, self.h)
            face_configs_message[f"cfg_{i}"] = self.create_crop_cfg(
                face_rect, img_detections
            )

        for group in (
            left_configs_message,
            right_configs_message,
            face_configs_message,
        ):
            group.setBufferMetadataFrom(img_detections)

        self.face_config_output.send(face_configs_message)
        self.left_config_output.send(left_configs_message)
        self.right_config_output.send(right_configs_message)

    def crop_rectangle(self, center_keypoint: dai.Point2f, crop_w: int, crop_h: int):
        return dai.RotatedRect(
            dai.Point2f(center_keypoint.x * self.w, center_keypoint.y * self.h, False),
            dai.Size2f(crop_w, crop_h, False),
            0,
        )

    def create_crop_cfg(
        self, rectangle: dai.RotatedRect, img_detections: dai.ImgDetections
    ):
        cfg = dai.ImageManipConfig()
        cfg.addCropRotatedRect(rectangle, normalizedCoords=False)
        cfg.setOutputSize(self.target_w, self.target_h)
        cfg.setReusePreviousImage(False)
        cfg.setBufferMetadataFrom(img_detections)

        return cfg

    def set_target_size(self, w: int, h: int):
        """Set the target size for the output image."""
        self.target_w, self.target_h = w, h
