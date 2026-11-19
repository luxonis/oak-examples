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
            plate_message = node.inputs["license_plate_detections"].get()
            license_plate_detections = plate_message.detections

            if len(license_plate_detections) == 0:
                continue

            license_plate_detection = sorted(
                license_plate_detections, key=lambda x: x.confidence, reverse=True
            )[0]
            if license_plate_detection.confidence < 0.5:
                continue

            license_plate_detection.setOuterBoundingBox(
                license_plate_detection.xmin * 1.02,
                license_plate_detection.ymin * 1.03,
                license_plate_detection.xmax * 0.98,
                license_plate_detection.ymax * 0.97,
            )

            plate_rect = plate_message.getTransformation().remapRectTo(
                frame.getTransformation(), license_plate_detection.getBoundingBox()
            )
            pixel_rect = plate_rect.denormalize(frame_w, frame_h)
            if pixel_rect.size.width <= 40 or pixel_rect.size.height <= 10:
                continue

            license_plate_detection.setBoundingBox(plate_rect)
            cfg = ImageManipConfig()
            cfg.addCropRotatedRect(plate_rect, normalizedCoords=True)
            cfg.setReusePreviousImage(False)
            cfg.setOutputSize(320, 48)
            cfg.setTimestamp(detections_message.getTimestamp())
            cfg.setTimestampDevice(detections_message.getTimestampDevice())
            cfg.setSequenceNum(detections_message.getSequenceNum())

            valid_detections.append(d)
            valid_crops.append(license_plate_detection)
            node.outputs["lp_crop_config"].send(cfg)
            node.outputs["lp_crop_frame"].send(frame)

        valid_detections_msg = ImgDetections()
        valid_detections_msg.detections = valid_detections
        valid_detections_msg.setTimestamp(detections_message.getTimestamp())
        valid_detections_msg.setTimestampDevice(detections_message.getTimestampDevice())
        valid_detections_msg.setSequenceNum(detections_message.getSequenceNum())
        valid_detections_msg.setTransformation(frame.getTransformation())

        valid_crops_msg = ImgDetections()
        valid_crops_msg.detections = valid_crops
        valid_crops_msg.setTimestamp(detections_message.getTimestamp())
        valid_crops_msg.setTimestampDevice(detections_message.getTimestampDevice())
        valid_crops_msg.setSequenceNum(detections_message.getSequenceNum())
        valid_crops_msg.setTransformation(frame.getTransformation())
        node.warn("sending vehicle crop config")
        node.outputs["output_valid_crops"].send(valid_crops_msg)
        node.outputs["output_valid_detections"].send(valid_detections_msg)

except Exception as e:
    node.warn(str(e))
