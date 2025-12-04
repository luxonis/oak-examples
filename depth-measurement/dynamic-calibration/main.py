import cv2

from depthai_nodes.node import ApplyColormap
import depthai as dai

from utils.dynamic_controler import DynamicCalibrationControler
from utils.arguments import initialize_argparser

_, args = initialize_argparser()

visualizer = dai.RemoteConnection(httpPort=8082)
device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()
# ---------- Pipeline definition ----------
with dai.Pipeline(device) as pipeline:
    # Create camera nodes
    cam_left = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_B)
    cam_right = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_C)

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

    # Dynamic calibration node
    dyn_calib = pipeline.create(dai.node.DynamicCalibration)
    left_out.link(dyn_calib.left)
    right_out.link(dyn_calib.right)

    # Output queues
    depth_parser = pipeline.create(ApplyColormap).build(stereo.disparity)
    # depth_parser.setMaxValue(int(stereo.initialConfig.getMaxDisparity())) # NOTE: Uncomment when DAI fixes a bug
    depth_parser.setColormap(cv2.COLORMAP_JET)

    calibration = device.readCalibration()
    new_calibration = None
    old_calibration = None

    # --- existing ---
    calibration_output = dyn_calib.calibrationOutput.createOutputQueue()
    coverage_output = dyn_calib.coverageOutput.createOutputQueue()
    quality_output = dyn_calib.qualityOutput.createOutputQueue()
    input_control = dyn_calib.inputControl.createInputQueue()
    device.setCalibration(calibration)

    # ---------- Visualizer setup ----------
    visualizer.addTopic("Left", stereo.syncedLeft, "images")
    visualizer.addTopic("Right", stereo.syncedRight, "images")
    visualizer.addTopic("Depth", depth_parser.out, "images")

    dyn_ctrl = pipeline.create(DynamicCalibrationControler).build(
        preview=depth_parser.out,  # for timestamped overlays
        depth=stereo.depth,  # raw uint16 depth in mm
    )
    visualizer.addTopic("DynCalib HUD", dyn_ctrl.out_annotations, "images")

    pipeline.start()
    visualizer.registerPipeline(pipeline)

    # give it queues
    dyn_ctrl.set_coverage_output(coverage_output)
    dyn_ctrl.set_calibration_output(calibration_output)
    dyn_ctrl.set_command_input(input_control)
    dyn_ctrl.set_quality_output(quality_output)
    dyn_ctrl.set_depth_units_is_mm(True)  # True for stereo.depth, False for disparity
    dyn_ctrl.set_device(device)

    # (optional) Set current calibration
    try:
        dyn_ctrl.set_current_calibration(device.readCalibration())
    except Exception:
        pass

    while pipeline.isRunning():
        key = visualizer.waitKey(1)
        if key != -1:
            dyn_ctrl.handle_key_press(key)
            if dyn_ctrl.wants_quit:
                break
