import depthai as dai
from depthai_nodes.node import ApplyColormap, ApplyDepthColormap

from utils.arguments import initialize_argparser
from utils.manual_camera_control import ManualCameraControl

_, args = initialize_argparser()

visualizer = dai.RemoteConnection(httpPort=8082)
device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()
platform = device.getPlatform().name
print(f"Platform: {platform}")

if platform != "RVC4":
    raise ValueError("This example is supported only on RVC4 platform")

if args.fps_limit is None:
    args.fps_limit = 10
    print(
        f"\nFPS limit set to {args.fps_limit} for {platform} platform. If you want to set a custom FPS limit, use the --fps_limit flag.\n"
    )


with dai.Pipeline(device) as pipeline:
    print("Creating pipeline...")

    # Create pipeline
    cameraLeft = pipeline.create(dai.node.Camera).build(
        dai.CameraBoardSocket.CAM_B, sensorFps=args.fps_limit
    )
    cameraRight = pipeline.create(dai.node.Camera).build(
        dai.CameraBoardSocket.CAM_C, sensorFps=args.fps_limit
    )
    leftOutput = cameraLeft.requestFullResolutionOutput()
    rightOutput = cameraRight.requestFullResolutionOutput()

    neuralDepth = pipeline.create(dai.node.NeuralDepth).build(
        leftOutput, rightOutput, args.model
    )

    manual_cam_control = pipeline.create(ManualCameraControl).build(
        frame=neuralDepth.disparity,
        control_queue=neuralDepth.inputConfig.createInputQueue(),
    )

    # Visualizations
    disp_out = pipeline.create(ApplyDepthColormap).build(neuralDepth.disparity)
    disp_out.setPercentileRange(low=2, high=98)

    conf_out = pipeline.create(ApplyColormap).build(neuralDepth.confidence)
    edge_out = pipeline.create(ApplyColormap).build(neuralDepth.edge)

    visualizer.addTopic("Disparity", disp_out.out)
    visualizer.addTopic("Confidence", conf_out.out)
    visualizer.addTopic("Edge", edge_out.out)
    visualizer.addTopic("Controls", manual_cam_control.out)

    print("Pipeline created.")

    pipeline.start()
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        key = visualizer.waitKey(1)

        if key == ord("q"):
            print("Got q key from the remote connection!")
            break
        else:
            manual_cam_control.handle_key_press(key)
