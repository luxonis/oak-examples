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
    args.fps_limit = 25  # if platform == "RVC2" else 30
    print(
        f"\nFPS limit set to {args.fps_limit} for {platform} platform. If you want to set a custom FPS limit, use the --fps_limit flag.\n"
    )

with dai.Pipeline(device) as pipeline:
    print("Creating pipeline...")

    # detection model
    det_model_description = dai.NNModelDescription.fromYamlFile(
        f"yolov6_nano_r2_coco.{platform}.yaml"
    )
    if det_model_description.model != args.model:
        det_model_description = dai.NNModelDescription(args.model, platform=platform)

    # media/camera input
    if args.media_path:
        replay = pipeline.create(dai.node.ReplayVideo)
        replay.setReplayVideoFile(Path(args.media_path))
        replay.setOutFrameType(frame_type)
        replay.setLoop(True)
    else:
        cam = pipeline.create(dai.node.Camera).build()
    input_node = replay if args.media_path else cam

    nn: ParsingNeuralNetwork = pipeline.create(ParsingNeuralNetwork).build(
        input_node, det_model_description, args.fps_limit
    )
    nn.setNumInferenceThreads(2)
    nn.input.setBlocking(False)

    # object tracking
    objectTracker = pipeline.create(dai.node.ObjectTracker)
    if platform == "RVC2":
        objectTracker.setTrackerType(dai.TrackerType.ZERO_TERM_COLOR_HISTOGRAM)
    else:
        objectTracker.setTrackerType(dai.TrackerType.SHORT_TERM_IMAGELESS)

    objectTracker.setTrackerIdAssignmentPolicy(
        dai.TrackerIdAssignmentPolicy.SMALLEST_ID
    )
    nn.passthrough.link(objectTracker.inputTrackerFrame)
    nn.passthrough.link(objectTracker.inputDetectionFrame)
    nn.out.link(objectTracker.inputDetections)

    # annotation
    annotation_node = pipeline.create(AnnotationNode).build(
        objectTracker.out, axis=args.axis, roi_position=args.roi_position
    )

    # visualization
    visualizer.addTopic("Video", nn.passthrough)
    visualizer.addTopic("Count", annotation_node.out)

    print("Pipeline created.")

    pipeline.start()
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        key_pressed = visualizer.waitKey(1)
        if key_pressed == ord("q"):
            print("Got q key. Exiting...")
            break
