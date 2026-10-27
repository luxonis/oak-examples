import depthai as dai
from depthai_nodes.node import ApplyColormap, ApplyDepthColormap

from utils.arguments import NATIVE_MODELS, initialize_argparser
from utils.las2 import build_las2
from utils.manual_camera_control import ManualCameraControl

_, args = initialize_argparser()

visualizer = dai.RemoteConnection(httpPort=8082)
device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()
platform = device.getPlatform().name
print(f"Platform: {platform}")

if platform != "RVC4":
    raise ValueError("This example is supported only on RVC4 platform")

sockets = {camera.socket for camera in device.getConnectedCameraFeatures()}
if not {dai.CameraBoardSocket.CAM_B, dai.CameraBoardSocket.CAM_C} <= sockets:
    raise ValueError(
        "This example requires a calibrated stereo pair on CAM_B and CAM_C"
    )

print(f"Depth backend: {args.backend}; model: {args.model}")

if args.fps_limit is None:
    args.fps_limit = 10
    print(
        f"\nFPS limit set to {args.fps_limit} for {platform} platform. If you want to set a custom FPS limit, use the --fps_limit flag.\n"
    )


with dai.Pipeline(device) as pipeline:
    print("Creating pipeline...")

    cameraLeft = pipeline.create(dai.node.Camera).build(
        dai.CameraBoardSocket.CAM_B, sensorFps=args.fps_limit
    )
    cameraRight = pipeline.create(dai.node.Camera).build(
        dai.CameraBoardSocket.CAM_C, sensorFps=args.fps_limit
    )
    leftOutput = cameraLeft.requestFullResolutionOutput(
        type=dai.ImgFrame.Type.GRAY8, fps=args.fps_limit
    )
    rightOutput = cameraRight.requestFullResolutionOutput(
        type=dai.ImgFrame.Type.GRAY8, fps=args.fps_limit
    )

    manual_cam_control = None
    if args.backend == "native":
        neuralDepth = pipeline.create(dai.node.NeuralDepth).build(
            leftOutput, rightOutput, NATIVE_MODELS[args.model]
        )

        manual_cam_control = pipeline.create(ManualCameraControl).build(
            frame=neuralDepth.disparity,
            control_queue=neuralDepth.inputConfig.createInputQueue(),
        )
        conf_out = pipeline.create(ApplyColormap).build(neuralDepth.confidence)
        edge_out = pipeline.create(ApplyColormap).build(neuralDepth.edge)
        visualizer.addTopic("Confidence", conf_out.out)
        visualizer.addTopic("Edge", edge_out.out)
        visualizer.addTopic("Controls", manual_cam_control.out)
    else:
        neuralDepth = build_las2(
            pipeline, leftOutput, rightOutput, args.model, device.readCalibration()
        )

    # Visualizations
    disp_out = pipeline.create(ApplyDepthColormap).build(neuralDepth.disparity)
    disp_out.setPercentileRange(low=2, high=98)

    depth_out = pipeline.create(ApplyDepthColormap).build(neuralDepth.depth)

    visualizer.addTopic("Disparity", disp_out.out)
    visualizer.addTopic("Depth", depth_out.out)

    print("Pipeline created.")
    pipeline.start()
    print("Pipeline started.")
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        key = visualizer.waitKey(1)

        if key == ord("q"):
            print("Got q key from the remote connection!")
            break
        elif manual_cam_control is not None:
            manual_cam_control.handle_key_press(key)
