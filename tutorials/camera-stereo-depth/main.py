import depthai as dai
from utils.arguments import initialize_argparser
from depthai_nodes.node import ApplyColormap
import cv2

_, args = initialize_argparser()

color_resolution = (1920, 1080)

visualizer = dai.RemoteConnection(httpPort=8082)
device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()
print("Device Information: ", device.getDeviceInfo())

print(device.getConnectedCameraFeatures())

with dai.Pipeline(device) as pipeline:
    print("Creating pipeline...")

    color = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_A)
    left = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_B)
    right = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_C)

    color_output = color.requestOutput(
        color_resolution, dai.ImgFrame.Type.NV12, fps=args.fps_limit
    )
    left_output = left.requestFullResolutionOutput(
        dai.ImgFrame.Type.NV12, fps=args.fps_limit
    )
    right_output = right.requestFullResolutionOutput(
        dai.ImgFrame.Type.NV12, fps=args.fps_limit
    )

    stereo = pipeline.create(dai.node.StereoDepth).build(
        left=left_output,
        right=right_output,
    )

    stereo.initialConfig.setMedianFilter(dai.MedianFilter.MEDIAN_OFF)
    stereo.setRectification(True)
    stereo.setExtendedDisparity(True)
    stereo.setLeftRightCheck(True)

    depth_parser = pipeline.create(ApplyColormap).build(stereo.disparity)
    # depth_parser.setMaxValue(int(stereo.initialConfig.getMaxDisparity())) # NOTE: Uncomment when DAI fixes a bug
    depth_parser.setColormap(cv2.COLORMAP_JET)

    encoder = pipeline.create(dai.node.VideoEncoder)
    encoder.setDefaultProfilePreset(
        args.fps_limit, dai.VideoEncoderProperties.Profile.H264_MAIN
    )
    color_output.link(encoder.input)

    visualizer.addTopic("Color", encoder.out, "images")
    visualizer.addTopic("Depth", depth_parser.out, "images")
    visualizer.addTopic("Left", left_output, "images")
    visualizer.addTopic("Right", right_output, "images")

    print("Pipeline created.")

    pipeline.start()
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got q key from the remote connection!")
            break
