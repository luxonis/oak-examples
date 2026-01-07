import depthai as dai

from utils.arguments import initialize_argparser
from utils.host_stream_output import StreamOutput

_, args = initialize_argparser()

device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()

visualizer = dai.RemoteConnection(httpPort=8082)

with dai.Pipeline(device) as pipeline:
    print("Creating pipeline...")
    cam = pipeline.create(dai.node.Camera).build()
    cam_out = cam.requestOutput(
        size=(640, 480), type=dai.ImgFrame.Type.NV12, fps=args.fps_limit
    )

    vid_enc = pipeline.create(dai.node.VideoEncoder)
    vid_enc.setDefaultProfilePreset(
        args.fps_limit, dai.VideoEncoderProperties.Profile.H265_MAIN
    )
    cam_out.link(vid_enc.input)

    node = pipeline.create(StreamOutput).build(
        stream=vid_enc.bitstream, fps=args.fps_limit
    )
    node.inputs["stream"].setBlocking(True)
    node.inputs["stream"].setMaxSize(args.fps_limit)

    visualizer.addTopic("Video", cam_out)

    print("Pipeline created. Watch the stream on rtsp://localhost:8554/preview")
    pipeline.start()
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        pipeline.processTasks()
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got q key from the remote connection!")
            break
