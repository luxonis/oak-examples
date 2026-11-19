import cv2
import depthai as dai
from depthai_nodes.node import ApplyDepthColormap
from utils.arguments import initialize_argparser
from utils.auto_calibration_status import AutoCalibrationStatus
from utils.camera import select_stereo_resolution

_, args = initialize_argparser()

visualizer = dai.RemoteConnection(httpPort=8082)
device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()
with device, dai.Pipeline(device) as pipeline:
    # Use the explicit node below instead of the SDK's implicit procedure.
    pipeline.setAutoCalibrationMode(dai.Pipeline.AutoCalibrationMode.OFF)
    resolution = select_stereo_resolution(device.getConnectedCameraFeatures())
    cam_left = pipeline.create(dai.node.Camera).build(
        dai.CameraBoardSocket.CAM_B,
        sensorResolution=resolution,
        sensorFps=args.fps_limit,
    )
    cam_right = pipeline.create(dai.node.Camera).build(
        dai.CameraBoardSocket.CAM_C,
        sensorResolution=resolution,
        sensorFps=args.fps_limit,
    )

    stereo = pipeline.create(dai.node.StereoDepth)
    cam_left.requestFullResolutionOutput(
        dai.ImgFrame.Type.NV12, fps=args.fps_limit
    ).link(stereo.left)
    cam_right.requestFullResolutionOutput(
        dai.ImgFrame.Type.NV12, fps=args.fps_limit
    ).link(stereo.right)

    # AutoCalibration manages its own DynamicCalibration worker and consumes
    # unrectified ISP frames from the same camera nodes.
    auto_calibration = pipeline.create(dai.node.AutoCalibration)
    auto_calibration.initialConfig.mode = (
        dai.AutoCalibrationConfig.ON_START
        if args.mode == "on-start"
        else dai.AutoCalibrationConfig.CONTINUOUS
    )
    # The native default is True. This example always keeps updates in RAM.
    auto_calibration.initialConfig.flashCalibration = False
    auto_calibration.initialConfig.sleepingTime = args.auto_interval
    auto_calibration.build(cam_left, cam_right)

    depth_preview = pipeline.create(ApplyDepthColormap).build(stereo.disparity)
    depth_preview.setColormap(cv2.COLORMAP_JET)
    status = pipeline.create(AutoCalibrationStatus).build(
        depth_preview.out, auto_calibration.output, args.mode, device.getCalibration()
    )

    visualizer.addTopic("Left", stereo.syncedLeft, "images")
    visualizer.addTopic("Right", stereo.syncedRight, "images")
    visualizer.addTopic("Depth", depth_preview.out, "images")
    visualizer.addTopic("AutoCalib HUD", status.out_annotations, "images")

    print(
        f"AutoCalibration {args.mode}: {resolution[0]}x{resolution[1]}, "
        "flashCalibration=False; native validation thresholds and retries enabled.",
        flush=True,
    )
    pipeline.start()
    print("Pipeline started.", flush=True)
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        if visualizer.waitKey(1) == ord("q"):
            break
