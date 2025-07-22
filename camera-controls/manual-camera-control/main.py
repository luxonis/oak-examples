import depthai as dai
from utils.arguments import initialize_argparser
from utils.manual_camera_control import ManualCameraControl

_, args = initialize_argparser()


visualizer = dai.RemoteConnection(httpPort=8082)
device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()

with dai.Pipeline(device) as pipeline:
    print("Creating pipeline...")

    cam = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_A)
    cam_out = cam.requestOutput(
        (1920, 1080), dai.ImgFrame.Type.NV12, fps=args.fps_limit
    )

    manual_cam_control = pipeline.create(ManualCameraControl).build(
        color_cam=cam_out,
        control_queue=cam.inputControl.createInputQueue(),
        fps=args.fps_limit,
    )

    visualizer.addTopic("Video", cam_out, "images")
    visualizer.addTopic("Camera Configuration", manual_cam_control.output, "images")

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
