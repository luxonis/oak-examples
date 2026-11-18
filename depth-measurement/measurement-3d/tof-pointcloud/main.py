import depthai as dai

from utils.arguments import initialize_argparser
from utils.tof_mode_control import MODES, DEFAULT_MODE_KEY, ToFModeControl

SIZE = (640, 400)

_, args = initialize_argparser()

visualizer = dai.RemoteConnection(httpPort=8082)
device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()
platform = device.getPlatform()

with dai.Pipeline(device) as pipeline:
    print("Creating pipeline...")

    rgb_socket = (
        dai.CameraBoardSocket.CAM_C
        if platform == dai.Platform.RVC2
        else dai.CameraBoardSocket.CAM_A
    )
    color = pipeline.create(dai.node.Camera).build(rgb_socket, sensorFps=args.fps_limit)
    color_out = color.requestOutput(
        SIZE,
        type=dai.ImgFrame.Type.RGB888i,
        fps=args.fps_limit,
        enableUndistortion=True,
    )
    video_out = color.requestOutput(
        SIZE, type=dai.ImgFrame.Type.NV12, fps=args.fps_limit
    )

    tof = pipeline.create(dai.node.ToF).build(
        boardSocket=dai.CameraBoardSocket.AUTO,
        presetMode=MODES[DEFAULT_MODE_KEY][2],
        fps=args.fps_limit,
    )

    align = pipeline.create(dai.node.ImageAlign)
    align.setRunOnHost(True)
    tof.depth.link(align.input)
    color_out.link(align.inputAlignTo)

    point_cloud = pipeline.create(dai.node.PointCloud)
    point_cloud.initialConfig.setLengthUnit(dai.LengthUnit.MILLIMETER)
    point_cloud.setTargetCoordinateSystem(rgb_socket)
    align.outputAligned.link(point_cloud.inputDepth)
    color_out.link(point_cloud.inputColor)

    encoder = pipeline.create(dai.node.VideoEncoder)
    encoder.setDefaultProfilePreset(
        args.fps_limit, dai.VideoEncoderProperties.Profile.MJPEG
    )
    video_out.link(encoder.input)

    # RVC4 applies ToF filtering on device; RVC2 needs the host filter preset too.
    mode_control = pipeline.create(ToFModeControl).build(
        frames=color_out,
        tof_config_queue=tof.tofBaseInputConfig.createInputQueue(),
        filter_config_queue=(
            tof.imageFiltersInputConfig.createInputQueue()
            if platform == dai.Platform.RVC2
            else None
        ),
    )

    visualizer.addTopic("Point Cloud", point_cloud.outputPointCloud, "3d")
    visualizer.addTopic("Color", encoder.out, "images")
    visualizer.addTopic("ToF Mode", mode_control.output, "images")

    print("Pipeline created.")
    pipeline.start()
    print("Pipeline started.")
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got q key from the remote connection!")
            break
        mode_control.handle_key_press(key)
