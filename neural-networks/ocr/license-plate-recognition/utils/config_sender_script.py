try:
    while True:
        frame = node.inputs["frame_input"].get()
        node.warn("got frame")
        detections_message = node.inputs["detections_input"].get()
        node.warn("got detections")
        vehicle_detections = []

        for d in detections_message.detections:
            if d.label not in [2, 5, 7]:  # not a car, bus or truck
                continue
            if d.confidence < 0.7:
                continue
            d.xmin = max(0, min(1, d.xmin * 0.9))
            d.ymin = max(0, min(1, d.ymin * 0.9))
            d.xmax = max(0, min(1, d.xmax * 1.1))
            d.ymax = max(0, min(1, d.ymax * 1.1))

            vehicle_detections.append(d)

            x_center = (d.xmin + d.xmax) / 2
            y_center = (d.ymin + d.ymax) / 2
            det_w = d.xmax - d.xmin
            det_h = d.ymax - d.ymin

            det_center = Point2f(x_center, y_center, normalized=True)
            det_size = Size2f(det_w, det_h, normalized=True)

            det_rect = RotatedRect(det_center, det_size, 0)
            det_rect = det_rect.denormalize(frame.getWidth(), frame.getHeight())

            cfg = ImageManipConfig()
            cfg.addCropRotatedRect(det_rect, normalizedCoords=False)
            cfg.setOutputSize(640, 640)
            cfg.setReusePreviousImage(False)
            cfg.setTimestamp(detections_message.getTimestamp())
            node.outputs["output_config"].send(cfg)
            node.outputs["output_frame"].send(frame)

        vehicle_detections_msg = ImgDetections()
        vehicle_detections_msg.detections = vehicle_detections
        vehicle_detections_msg.setTimestamp(detections_message.getTimestamp())
        vehicle_detections_msg.setTransformation(detections_message.getTransformation())

        node.warn("sending vehicle crop config")
        node.outputs["output_vehicle_detections"].send(vehicle_detections_msg)

except Exception as e:
    node.warn(str(e))
