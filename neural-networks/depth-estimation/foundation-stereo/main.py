import depthai as dai
from depthai_nodes.node import ApplyColormap

from utils.arguments import initialize_argparser
from utils.utility import get_resolution_profile
from utils.fs_inferer import FSInferer

_, args = initialize_argparser()

fps = args.fps_limit
resolution_profile = get_resolution_profile(args.resolution)

visualizer = dai.RemoteConnection(httpPort=8082)
device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()

device.setIrLaserDotProjectorIntensity(1)

with dai.Pipeline(device) as pipeline:
    print("Creating pipeline...")

    # Check if the device has color, left and right cameras
    available_cameras = device.getConnectedCameras()

    if len(available_cameras) < 3:
        raise ValueError(
            "Device must have 3 cameras (color, left and right) in order to run this experiment."
        )

    monoLeft = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_B)
    monoRight = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_C)
    stereo = pipeline.create(dai.node.StereoDepth)

    monoLeftOut = monoLeft.requestOutput(
        size=resolution_profile.stereo_shape, fps=fps, enableUndistortion=False
    )
    monoRightOut = monoRight.requestOutput(
        size=resolution_profile.stereo_shape, fps=fps, enableUndistortion=False
    )

    monoLeftOut.link(stereo.left)
    monoRightOut.link(stereo.right)

    stereo.setExtendedDisparity(True)
    stereo.setLeftRightCheck(True)

    fs_inferer = pipeline.create(FSInferer).build(
        rect_left=stereo.rectifiedLeft,
        rect_right=stereo.rectifiedRight,
        stereo_disparity=stereo.disparity,
        inference_shape=resolution_profile.nn_shape,
    )

    colored_disp = pipeline.create(ApplyColormap).build(stereo.disparity)

    visualizer.addTopic("FS Result", fs_inferer.output)
    visualizer.addTopic("Disparity", colored_disp.out)
    visualizer.addTopic("Rectified right", stereo.rectifiedRight)
    visualizer.addTopic("Rectified left", stereo.rectifiedLeft)

    print("Pipeline created.")

    pipeline.start()
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got q key from the remote connection!")
            break
        if key == ord("f"):
            fs_inferer.infer()
