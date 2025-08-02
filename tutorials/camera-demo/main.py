import depthai as dai
from utils.arguments import initialize_argparser

_, args = initialize_argparser()

visualizer = dai.RemoteConnection(httpPort=8082)
device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()
print("Device Information: ", device.getDeviceInfo())

cam_features = {}
for cam in device.getConnectedCameraFeatures():
    cam_features[cam.socket] = (cam.width, cam.height)

with dai.Pipeline(device) as pipeline:
    print("Creating pipeline...")

    output_queues = {}
    camera_sensors = device.getConnectedCameraFeatures()
    for sensor in camera_sensors:
        cam = pipeline.create(dai.node.Camera).build(sensor.socket)

        request_resolution = (
            (sensor.width, sensor.height)
            if sensor.width <= 1920 and sensor.height <= 1080
            else (1920, 1080)
        )  # limit frame size to 1080p
        cam_out = cam.requestOutput(
            request_resolution, dai.ImgFrame.Type.NV12, fps=args.fps_limit
        )

        encoder = pipeline.create(dai.node.VideoEncoder)
        encoder.setDefaultProfilePreset(
            args.fps_limit, dai.VideoEncoderProperties.Profile.H264_MAIN
        )
        cam_out.link(encoder.input)

        visualizer.addTopic(sensor.socket.name, encoder.out, "images")

    print("Pipeline created.")

    pipeline.start()
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got q key from the remote connection!")
            break
