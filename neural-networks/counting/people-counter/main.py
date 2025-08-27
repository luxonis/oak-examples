from pathlib import Path

import depthai as dai
from depthai_nodes.node import ParsingNeuralNetwork, ImgDetectionsFilter

from utils.arguments import initialize_argparser
from utils.annotation_node import AnnotationNode

_, args = initialize_argparser()

visualizer = dai.RemoteConnection(httpPort=8082)
device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()
platform = device.getPlatform().name
print(f"Platform: {platform}")

frame_type = (
    dai.ImgFrame.Type.BGR888i if platform == "RVC4" else dai.ImgFrame.Type.BGR888p
)

if args.fps_limit is None:
    args.fps_limit = 10 if platform == "RVC2" else 30
    print(
        f"\nFPS limit set to {args.fps_limit} for {platform} platform. If you want to set a custom FPS limit, use the --fps_limit flag.\n"
    )

with dai.Pipeline(device) as pipeline:
    print("Creating pipeline...")

    # person detection model
    det_model_description = dai.NNModelDescription.fromYamlFile(
        f"scrfd_person_detection_25g.{platform}.yaml"
    )
    if det_model_description.model != args.model:
        det_model_description = dai.NNModelDescription(args.model, platform=platform)
    det_model_nn_archive = dai.NNArchive(dai.getModelFromZoo(det_model_description))

    # media/camera input
    if args.media_path:
        replay = pipeline.create(dai.node.ReplayVideo)
        replay.setReplayVideoFile(Path(args.media_path))
        replay.setOutFrameType(frame_type)
        replay.setLoop(True)
    else:
        cam = pipeline.create(dai.node.Camera).build()
    input_node = replay if args.media_path else cam

    det_nn: ParsingNeuralNetwork = pipeline.create(ParsingNeuralNetwork).build(
        input_node, det_model_nn_archive, fps=args.fps_limit
    )

    # person detection filter
    classes = det_model_nn_archive.getConfig().model.heads[0].metadata.classes
    labels_to_keep = [classes.index("person")] if "person" in classes else []
    det_filter = pipeline.create(ImgDetectionsFilter).build(
        det_nn.out, labels_to_keep=labels_to_keep, confidence_threshold=0.5
    )

    # annotation
    annotation_node = pipeline.create(AnnotationNode).build(det_filter.out)

    # visualization
    visualizer.addTopic("Video", det_nn.passthrough)
    visualizer.addTopic("PersonDetections", det_filter.out)
    visualizer.addTopic("PersonCount", annotation_node.out)

    print("Pipeline created.")

    pipeline.start()
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got q key. Exiting...")
            break
