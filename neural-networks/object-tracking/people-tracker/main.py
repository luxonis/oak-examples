from pathlib import Path

import depthai as dai
from depthai_nodes.node import ParsingNeuralNetwork, ImgDetectionsBridge

from utils.arguments import initialize_argparser
from utils.people_counter import PeopleCounter
from utils.tracklet_visualizer import TrackletVisualizer

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

    # detection model
    model_description = dai.NNModelDescription.fromYamlFile(
        f"scrfd_person_detection_25g.{platform}.yaml"
    )
    nn_archive = dai.NNArchive(dai.getModelFromZoo(model_description))

    # media/camera input
    if args.media_path:
        replay = pipeline.create(dai.node.ReplayVideo)
        replay.setReplayVideoFile(Path(args.media_path))
        replay.setOutFrameType(frame_type)
        replay.setLoop(True)
    else:
        cam = pipeline.create(dai.node.Camera).build()
    input_node = replay if args.media_path else cam

    nn = pipeline.create(ParsingNeuralNetwork).build(
        input_node, nn_archive, fps=args.fps_limit
    )

    # tracking
    bridge = pipeline.create(ImgDetectionsBridge).build(nn.out, ignore_angle=True)

    tracker = pipeline.create(dai.node.ObjectTracker)
    tracker.setDetectionLabelsToTrack([0])
    if platform == "RVC2":
        tracker.setTrackerType(dai.TrackerType.ZERO_TERM_COLOR_HISTOGRAM)
    else:
        tracker.setTrackerType(dai.TrackerType.SHORT_TERM_IMAGELESS)
    tracker.setTrackerIdAssignmentPolicy(dai.TrackerIdAssignmentPolicy.UNIQUE_ID)
    tracker.setTrackerThreshold(0.4)
    nn.passthrough.link(tracker.inputTrackerFrame)
    nn.passthrough.link(tracker.inputDetectionFrame)
    bridge.out.link(tracker.inputDetections)

    # annotation
    tracklet_visualizer = pipeline.create(TrackletVisualizer).build(
        tracklets=tracker.out,
        labels=nn_archive.getConfigV1().model.heads[0].metadata.classes,
    )

    people_counter = pipeline.create(PeopleCounter).build(
        tracklets=tracker.out, threshold=args.threshold
    )

    # visualization
    visualizer.addTopic("Video", nn.passthrough, "images")
    visualizer.addTopic("Tracklets", tracklet_visualizer.out, "images")
    visualizer.addTopic("People count", people_counter.out, "images")

    print("Pipeline created.")

    pipeline.start()
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got q key. Exiting...")
            break
