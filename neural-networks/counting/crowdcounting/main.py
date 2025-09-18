from pathlib import Path

import depthai as dai
from depthai_nodes.node import ParsingNeuralNetwork, ImgFrameOverlay, ApplyColormap

from utils.arguments import initialize_argparser
from utils.annotation_node import AnnotationNode

_, args = initialize_argparser()

visualizer = dai.RemoteConnection(httpPort=8082)
device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()
platform = device.getPlatform().name
print(f"Platform: {platform}")

frame_type = (
    dai.ImgFrame.Type.BGR888p if platform == "RVC2" else dai.ImgFrame.Type.BGR888i
)

if args.fps_limit is None:
    args.fps_limit = 2 if platform == "RVC2" else 5
    print(
        f"\nFPS limit set to {args.fps_limit} for {platform} platform. If you want to set a custom FPS limit, use the --fps_limit flag.\n"
    )

with dai.Pipeline(device) as pipeline:
    print("Creating pipeline...")

    # crowd counting model
    cc_model_description = dai.NNModelDescription.fromYamlFile(
        f"dm_count_shb.{platform}.yaml"
    )
    if cc_model_description.model != args.model:
        cc_model_description = dai.NNModelDescription(args.model, platform=platform)

    # media/camera input
    if args.media_path:
        replay = pipeline.create(dai.node.ReplayVideo)
        replay.setReplayVideoFile(Path(args.media_path))
        replay.setOutFrameType(frame_type)
        replay.setLoop(True)
    else:
        cam = pipeline.create(dai.node.Camera).build()
    input_node = replay if args.media_path else cam

    cc_nn: ParsingNeuralNetwork = pipeline.create(ParsingNeuralNetwork).build(
        input_node, cc_model_description, fps=args.fps_limit
    )

    # crowd density overlay
    color_transform_node = pipeline.create(ApplyColormap).build(cc_nn.out)
    overlay_node = pipeline.create(ImgFrameOverlay).build(
        cc_nn.passthrough,
        color_transform_node.out,
    )

    # annotation
    annotation_node = pipeline.create(AnnotationNode).build(cc_nn.out)

    # visualization
    visualizer.addTopic("VideoOverlay", overlay_node.out)
    visualizer.addTopic("Count", annotation_node.out)

    print("Pipeline created.")

    pipeline.start()
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        key_pressed = visualizer.waitKey(1)
        if key_pressed == ord("q"):
            print("Got q key. Exiting...")
            break
