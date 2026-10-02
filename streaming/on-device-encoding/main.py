import depthai as dai
from utils.arguments import initialize_argparser
from utils.video_saver import VideoSaver

_, args = initialize_argparser()

visualizer = dai.RemoteConnection(httpPort=8082)
device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()
platform = device.getPlatform().name

encoder_profiles = {
    "h264": dai.VideoEncoderProperties.Profile.H264_MAIN,
    "h265": dai.VideoEncoderProperties.Profile.H265_MAIN,
    "mjpeg": dai.VideoEncoderProperties.Profile.MJPEG,
}

with dai.Pipeline(device) as pipeline:
    print("Creating pipeline...")
    cam = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_A)
    cam_out = cam.requestOutput(
        size=(640, 480), type=dai.ImgFrame.Type.NV12, fps=args.fps_limit
    )

    video_enc = pipeline.create(dai.node.VideoEncoder)
    video_enc.setDefaultProfilePreset(
        fps=args.fps_limit, profile=encoder_profiles[args.codec]
    )
    cam_out.link(video_enc.input)

    video_saver = pipeline.create(VideoSaver).build(
        encoded_stream=video_enc.out,
        codec=args.codec,
        output_shape=(640, 480),
        fps=args.fps_limit,
        output_path=args.output,
    )

    # Visualizer currently doesn't support H265 or any encoded videos in RVC4 standalone mode - use non-encoded streams instead
    if args.codec == "h265" or device.getPlatform() == dai.Platform.RVC4:
        visualizer.addTopic("Video", cam_out, "images")
    else:
        visualizer.addTopic("Video", video_enc.out, "images")

    print("Pipeline created.")
    pipeline.start()
    print("Pipeline started.")
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got q key from the remote connection!")
            break
