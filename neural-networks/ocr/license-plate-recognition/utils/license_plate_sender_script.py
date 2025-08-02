def denormalize_detection(detection: ImgDetection, width: int, height: int):
    x_min, y_min, x_max, y_max = (
        detection.xmin,
        detection.ymin,
        detection.xmax,
        detection.ymax,
    )

    x_min = int(x_min * width)
    y_min = int(y_min * height)
    x_max = int(x_max * width)
    y_max = int(y_max * height)

    return x_min, y_min, x_max, y_max


try:
    while True:
        frame = node.inputs["frame_input"].get()
        frame_w = frame.getWidth()
        frame_h = frame.getHeight()

        detections_message = node.inputs["detections_input"].get()
        detections = detections_message.detections

        valid_detections = []
        valid_crops = []
        for d in detections:
            x_min, y_min, x_max, y_max = denormalize_detection(d, frame_w, frame_h)
            w = x_max - x_min
            h = y_max - y_min

            license_plate_detections = (
                node.inputs["license_plate_detections"].get().detections
            )

            if len(license_plate_detections) == 0:
                continue

            license_plate_detection = sorted(
                license_plate_detections, key=lambda x: x.confidence, reverse=True
            )[0]
            if license_plate_detection.confidence < 0.5:
                continue

            license_plate_detection.xmin = license_plate_detection.xmin * 1.02
            license_plate_detection.ymin = license_plate_detection.ymin * 1.03
            license_plate_detection.xmax = license_plate_detection.xmax * 0.98
            license_plate_detection.ymax = license_plate_detection.ymax * 0.97

            lp_x_min, lp_y_min, lp_x_max, lp_y_max = denormalize_detection(
                license_plate_detection, w, h
            )
            lp_w = lp_x_max - lp_x_min
            lp_h = lp_y_max - lp_y_min

            crop_x_min = max(0, min(lp_x_min + x_min, frame_w))
            crop_y_min = max(0, min(lp_y_min + y_min, frame_h))
            crop_w = max(0, min(lp_w, frame_w - crop_x_min))
            crop_h = max(0, min(lp_h, frame_h - crop_y_min))

            if crop_w <= 40 or crop_h <= 10:
                continue

            cfg = ImageManipConfig()
            cfg.addCrop(crop_x_min, crop_y_min, crop_w, crop_h)
            cfg.setReusePreviousImage(False)
            cfg.setOutputSize(320, 48)
            cfg.setTimestamp(detections_message.getTimestamp())

            valid_detections.append(d)
            valid_crops.append(license_plate_detection)
            node.outputs["lp_crop_config"].send(cfg)
            node.outputs["lp_crop_frame"].send(frame)

        valid_detections_msg = ImgDetections()
        valid_detections_msg.detections = valid_detections
        valid_detections_msg.setTimestamp(detections_message.getTimestamp())

        valid_crops_msg = ImgDetections()
        valid_crops_msg.detections = valid_crops
        valid_crops_msg.setTimestamp(detections_message.getTimestamp())
        node.warn("sending vehicle crop config")
        node.outputs["output_valid_crops"].send(valid_crops_msg)
        node.outputs["output_valid_detections"].send(valid_detections_msg)

except Exception as e:
    node.warn(str(e))
