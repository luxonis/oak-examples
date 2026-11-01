import cv2
import depthai as dai
from depthai_nodes.node import ApplyDepthColormap
from utils.arguments import initialize_argparser
from utils.auto_calibration import build_auto_calibration, select_stereo_resolution
from utils.dynamic_controler import DynamicCalibrationControler

_, args = initialize_argparser()

visualizer = dai.RemoteConnection(httpPort=8082)
device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()
# ---------- Pipeline definition ----------
with dai.Pipeline(device) as pipeline:
    # Use our explicit calibration nodes rather than the SDK's implicit procedure.
    pipeline.setAutoCalibrationMode(dai.Pipeline.AutoCalibrationMode.OFF)
    resolution = (
        select_stereo_resolution(device.getConnectedCameraFeatures())
        if args.mode != "manual"
        else None
    )
    # Create camera nodes
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

    # Request full resolution NV12 outputs
    left_out = cam_left.requestFullResolutionOutput(
        dai.ImgFrame.Type.NV12, fps=args.fps_limit
    )
    right_out = cam_right.requestFullResolutionOutput(
        dai.ImgFrame.Type.NV12, fps=args.fps_limit
    )

    # Stereo node
    stereo = pipeline.create(dai.node.StereoDepth)
    left_out.link(stereo.left)
    right_out.link(stereo.right)

    # Output queues
    depth_parser = pipeline.create(ApplyDepthColormap).build(stereo.disparity)
    depth_parser.setColormap(cv2.COLORMAP_JET)

    # ---------- Visualizer setup ----------
    visualizer.addTopic("Left", stereo.syncedLeft, "images")
    visualizer.addTopic("Right", stereo.syncedRight, "images")
    visualizer.addTopic("Depth", depth_parser.out, "images")

    dyn_ctrl = pipeline.create(DynamicCalibrationControler).build(
        preview=depth_parser.out,  # for timestamped overlays
        depth=stereo.depth,  # raw uint16 depth in mm
    )
    visualizer.addTopic("DynCalib HUD", dyn_ctrl.out_annotations, "images")

    if args.mode == "manual":
        dyn_calib = pipeline.create(dai.node.DynamicCalibration)
        left_out.link(dyn_calib.left)
        right_out.link(dyn_calib.right)
        dyn_ctrl.set_coverage_output(dyn_calib.coverageOutput.createOutputQueue())
        dyn_ctrl.set_calibration_output(dyn_calib.calibrationOutput.createOutputQueue())
        dyn_ctrl.set_command_input(dyn_calib.inputControl.createInputQueue())
        dyn_ctrl.set_quality_output(dyn_calib.qualityOutput.createOutputQueue())
        dyn_ctrl.set_device(device)
    else:
        worker = build_auto_calibration(
            pipeline, cam_left, cam_right, args.mode, args.auto_interval
        )
        dyn_ctrl.set_automatic_mode(args.mode, worker.output.createOutputQueue())
        print(
            f"AutoCalibration {args.mode}: {resolution[0]}x{resolution[1]}, "
            f"flashCalibration=False, validationSetSize={worker.initialConfig.validationSetSize}, "
            f"calibrationConfidenceThreshold={worker.initialConfig.calibrationConfidenceThreshold}, "
            "dataConfidenceThreshold=SDK lens-specific default",
            flush=True,
        )

    dyn_ctrl.set_depth_units_is_mm(True)  # True for stereo.depth, False for disparity
    dyn_ctrl.set_current_calibration(device.getCalibration())

    pipeline.start()
    visualizer.registerPipeline(pipeline)
    print(f"Pipeline started ({args.mode}).", flush=True)

    while pipeline.isRunning():
        key = visualizer.waitKey(1)
        if key != -1:
            dyn_ctrl.handle_key_press(key)
            if dyn_ctrl.wants_quit:
                break
