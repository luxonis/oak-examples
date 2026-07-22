#!/usr/bin/env python3

import cv2
import depthai as dai
from utils.roi_control import ROIControl
from utils.arguments import initialize_argparser
from depthai_nodes.node import ApplyDepthColormap
from utils.measure_distance import MeasureDistance


_, args = initialize_argparser()

visualizer = dai.RemoteConnection(httpPort=8082)
device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()
with dai.Pipeline(device) as pipeline:
    depth = pipeline.create(dai.node.Depth)
    depth.build(dai.node.Depth.Algorithm.AUTO, size=(640, 400))

    depth_color_transform = pipeline.create(ApplyDepthColormap).build(depth.depth)
    depth_color_transform.setColormap(cv2.COLORMAP_JET)

    measure_distance = pipeline.create(MeasureDistance).build(
        depth.depth, device.readCalibration(), ROIControl.INITIAL_ROI
    )

    calibdata = device.readCalibration()
    spatials = pipeline.create(ROIControl).build(
        depth_frames=depth_color_transform.out,
        measured_depth=measure_distance.output,
    )
    spatials.output_roi.link(measure_distance.roi_input)

    visualizer.addTopic("Depth", spatials.passthrough)
    visualizer.addTopic("Spatial Calculations", spatials.annotation_output)

    print("Pipeline created.")
    pipeline.start()
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got q key from the remote connection!")
            break
        else:
            spatials.handle_key_press(key)
