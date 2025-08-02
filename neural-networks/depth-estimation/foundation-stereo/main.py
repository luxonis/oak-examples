import depthai as dai
from depthai_nodes.node import ApplyColormap

from utils.arguments import initialize_argparser
from utils.fs_inferer import FSInferer

_, args = initialize_argparser()

device_info = args.device
fps = args.fps_limit

if args.resolution == 400:
    inference_shape = (416, 640)  # H,W format
elif args.resolution == 800:
    inference_shape = (800, 1280)
else:
    print("Invalid resolution, exiting.")
    exit(1)

visualizer = dai.RemoteConnection(httpPort=8082)
device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()

# TODO: Is there a nicer solution?
if len(device.getIrDrivers()) != 0:
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

    if args.resolution == 800:
        monoLeftOut = monoLeft.requestOutput(
            size=(1280, 800), fps=fps, enableUndistortion=True
        )
        monoRightOut = monoRight.requestOutput(
            size=(1280, 800), fps=fps, enableUndistortion=True
        )
    else:
        monoLeftOut = monoLeft.requestOutput(
            size=(640, 400), fps=fps, enableUndistortion=True
        )
        monoRightOut = monoRight.requestOutput(
            size=(640, 400), fps=fps, enableUndistortion=True
        )

    monoLeftOut.link(stereo.left)
    monoRightOut.link(stereo.right)

    stereo.setExtendedDisparity(True)
    stereo.setLeftRightCheck(True)

    fs_inferer = pipeline.create(FSInferer).build(
        rect_left=stereo.rectifiedLeft,
        rect_right=stereo.rectifiedRight,
        stereo_disparity=stereo.disparity,
        model_path=args.model,
        inference_shape=inference_shape,
    )

    colored_disp = pipeline.create(ApplyColormap).build(stereo.disparity)

    visualizer.addTopic("Disparity", colored_disp.out)
    visualizer.addTopic("Rectified right", stereo.rectifiedRight)
    visualizer.addTopic("Rectified left", stereo.rectifiedLeft)
    visualizer.addTopic("FS Result", fs_inferer.output)

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
