import depthai as dai

from utils.arguments import initialize_argparser
from utils.host_stereo_sgbm import StereoSGBM
from utils.host_ssim import SSIM
from depthai_nodes.node import ApplyColormap
import cv2

RESOLUTION_SIZE = (640, 400)

_, args = initialize_argparser()

visualizer = dai.RemoteConnection(httpPort=8082)
device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()
with dai.Pipeline(device) as pipeline:
    mono_left = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_B)
    mono_right = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_C)

    left = mono_left.requestOutput(size=RESOLUTION_SIZE, type=dai.ImgFrame.Type.NV12)
    right = mono_right.requestOutput(size=RESOLUTION_SIZE, type=dai.ImgFrame.Type.NV12)

    cams = device.getConnectedCameras()
    depth_enabled = (
        dai.CameraBoardSocket.CAM_B in cams and dai.CameraBoardSocket.CAM_C in cams
    )
    if not depth_enabled:
        raise RuntimeError(
            "Unable to run this example on device without left & right cameras! (Available cameras: {})".format(
                cams
            )
        )

    calibObj = device.readCalibration()

    stereoSGBM = pipeline.create(StereoSGBM).build(
        monoLeftOut=left,
        monoRightOut=right,
        calibObj=calibObj,
        device=device,
        resolution=RESOLUTION_SIZE,
    )
    stereoSGBM.inputs["monoLeft"].setBlocking(False)
    stereoSGBM.inputs["monoLeft"].setMaxSize(2)
    stereoSGBM.inputs["monoRight"].setBlocking(False)
    stereoSGBM.inputs["monoRight"].setMaxSize(2)

    stereo = pipeline.create(dai.node.StereoDepth).build(
        left=left, right=right, presetMode=dai.node.StereoDepth.PresetMode.FAST_DENSITY
    )
    stereo.setLeftRightCheck(True)
    stereo.setExtendedDisparity(False)
    stereo.setSubpixel(True)

    depth_parser = pipeline.create(ApplyColormap).build(stereo.disparity)
    depth_parser.setMaxValue(int(stereo.initialConfig.getMaxDisparity()))
    depth_parser.setColormap(cv2.COLORMAP_JET)

    ssim = pipeline.create(SSIM).build(
        disp_generated=stereo.disparity, disp_calculated=stereoSGBM.raw_disparity_out
    )
    ssim.setMaxGenDisparity(int(stereo.initialConfig.getMaxDisparity()))
    ssim.setMaxCalDisparity(int(stereoSGBM.max_disparity))

    visualizer.addTopic("Left Cam", stereoSGBM.mono_left)
    visualizer.addTopic("Right Cam", stereoSGBM.mono_right)
    visualizer.addTopic("Rectified Left", stereoSGBM.rectified_left)
    visualizer.addTopic("Rectified Right", stereoSGBM.rectified_right)

    visualizer.addTopic("Depth generated", depth_parser.out, "depth")
    visualizer.addTopic("Depth SGBM", stereoSGBM.disparity_out, "depth")
    visualizer.addTopic("SSIM score", ssim.output, "depth")

    print("Pipeline created.")

    pipeline.start()
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got q key from the remote connection!")
            break
