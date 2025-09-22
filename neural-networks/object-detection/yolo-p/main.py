from pathlib import Path

import depthai as dai
from depthai_nodes.node import ParsingNeuralNetwork

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
    args.fps_limit = 8
    print(
        f"\nFPS limit set to {args.fps_limit} for {platform} platform. If you want to set a custom FPS limit, use the --fps_limit flag.\n"
    )

with dai.Pipeline(device) as pipeline:
    print("Creating pipeline...")

    # yolo-p model
    model_description = dai.NNModelDescription.fromYamlFile(
        f"yolop_bdd100k.{platform}.yaml"
    )
    nn_archive = dai.NNArchive(dai.getModelFromZoo(model_description))
    model_w, model_h = nn_archive.getInputSize()

    # media/camera input
    if args.media_path:
        replay = pipeline.create(dai.node.ReplayVideo)
        replay.setReplayVideoFile(Path(args.media_path))
        replay.setOutFrameType(frame_type)
        replay.setLoop(True)
        if args.fps_limit:
            replay.setFps(args.fps_limit)
        replay.setSize(model_w, model_h)
    else:
        cam = pipeline.create(dai.node.Camera).build()
        cam_out = cam.requestOutput(
            size=(model_w, model_h), type=frame_type, fps=args.fps_limit
        )

    input_node_out = replay.out if args.media_path else cam_out

    nn: ParsingNeuralNetwork = pipeline.create(ParsingNeuralNetwork).build(
        input_node_out, nn_archive
    )

    # annotation
    annotation_node = pipeline.create(AnnotationNode).build(
        frame=input_node_out,
        detections=nn.getOutput(0),
        road_segmentations=nn.getOutput(1),
        lane_segmentations=nn.getOutput(2),
    )

    # visualization
    visualizer.addTopic(
        "Road Segmentation", annotation_node.out_segmentations, "images"
    )
    visualizer.addTopic("Detections", annotation_node.out_detections, "images")

    print("Pipeline created.")

    pipeline.start()
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got q key. Exiting...")
            break
