from pathlib import Path

import depthai as dai
from utils.arguments import initialize_argparser
from utils.encoder_profiles import ENCODER_PROFILES

_, args = initialize_argparser()

if args.encode == "h265":
    print(
        "Playing H265 encoded stream using Visualizer is currently not supported. Using H264 encoding."
    )
    args.encode = "h264"

visualizer = dai.RemoteConnection(httpPort=8082)
device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()


with dai.Pipeline(device) as pipeline:
    print("Creating pipeline...")

    platform = device.getPlatformAsString()

    if args.media_path:
        replay = pipeline.create(dai.node.ReplayVideo)
        replay.setReplayVideoFile(Path(args.media_path))
        replay.setOutFrameType(dai.ImgFrame.Type.NV12)
        replay.setLoop(True)
        cam_out = replay.out
    else:
        cam = pipeline.create(dai.node.Camera).build()
        cam_out = cam.requestOutput((1920, 1440), type=dai.ImgFrame.Type.NV12)

    encoder = pipeline.create(dai.node.VideoEncoder).build(
        input=cam_out,
        frameRate=args.fps_limit,
        profile=ENCODER_PROFILES[args.encode],
    )

    visualizer.addTopic("Video", encoder.out)
    print("Pipeline created.")
    pipeline.start()
    print("Pipeline started.")
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got q key from the remote connection!")
            break
