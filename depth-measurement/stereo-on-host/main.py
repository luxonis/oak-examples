import cv2
import depthai as dai
from depthai_nodes.node import ApplyDepthColormap
from utils.arguments import initialize_argparser
from utils.host_ssim import SSIM
from utils.host_stereo_sgbm import StereoSGBM

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
            f"Unable to run this example on device without left & right cameras! (Available cameras: {cams})"
        )

    stereo = pipeline.create(dai.node.StereoDepth).build(
        left=left, right=right, presetMode=dai.node.StereoDepth.PresetMode.FAST_DENSITY
    )
    stereo.setLeftRightCheck(True)
    stereo.setExtendedDisparity(False)
    stereo.setSubpixel(True)

    # Both matchers use this calibrated, distortion-corrected geometry.
    stereo.enableDistortionCorrection(True)
    stereo.setRectificationUseSpecTranslation(False)
    stereo.setDisparityToDepthUseSpecTranslation(False)
    stereo.setDepthAlign(
        dai.StereoDepthConfig.AlgorithmControl.DepthAlign.RECTIFIED_LEFT
    )
    stereo.setRectifyEdgeFillColor(0)

    stereoSGBM = pipeline.create(StereoSGBM).build(
        stereo.rectifiedLeft, stereo.rectifiedRight
    )

    depth_parser = pipeline.create(ApplyDepthColormap).build(stereo.disparity)
    depth_parser.setColormap(cv2.COLORMAP_JET)

    ssim = pipeline.create(SSIM).build(
        disp_generated=stereo.disparity,
        disp_calculated=stereoSGBM.raw_disparity_out,
        generated_scale=1 << stereo.initialConfig.getSubpixelFractionalBits(),
    )
    visualizer.addTopic("Left Cam", left)
    visualizer.addTopic("Right Cam", right)
    visualizer.addTopic("Rectified Left", stereo.rectifiedLeft)
    visualizer.addTopic("Rectified Right", stereo.rectifiedRight)

    visualizer.addTopic("Depth generated", depth_parser.out, "depth")
    visualizer.addTopic("Depth SGBM", stereoSGBM.disparity_out, "depth")
    visualizer.addTopic("SSIM score", ssim.output, "depth")

    print("Pipeline created.")
    pipeline.start()
    print("Pipeline started.")
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got q key from the remote connection!")
            break
