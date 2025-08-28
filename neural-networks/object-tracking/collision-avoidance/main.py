import depthai as dai

from depthai_nodes.node import ImgDetectionsFilter

from utils.collision_avoidance_node import CollisionAvoidanceNode
from utils.host_bird_eye_view import BirdsEyeView
from utils.arguments import initialize_argparser

_, args = initialize_argparser()

visualizer = dai.RemoteConnection(httpPort=8082)
device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()
platform = device.getPlatform().name
print(f"Platform: {platform}")

if args.fps_limit is None:
    args.fps_limit = 20 if platform == "RVC2" else 30
    print(
        f"\nFPS limit set to {args.fps_limit} for {platform} platform. If you want to set a custom FPS limit, use the --fps_limit flag.\n"
    )

if len(device.getConnectedCameras()) < 3:
    raise ValueError(
        "Device must have 3 cameras (color, left and right) in order to run this example."
    )


with dai.Pipeline(device) as pipeline:
    print("Creating pipeline...")

    # detection model
    model_description = dai.NNModelDescription.fromYamlFile(
        f"yolov6_nano_r2_coco.{platform}.yaml"
    )
    nn_archive = dai.NNArchive(dai.getModelFromZoo(model_description))
    labels = nn_archive.getConfig().model.heads[0].metadata.classes
    person_label = labels.index("person")

    # camera input
    cam = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_A)

    left_cam = pipeline.create(dai.node.Camera).build(
        dai.CameraBoardSocket.CAM_B, sensorFps=args.fps_limit
    )
    right_cam = pipeline.create(dai.node.Camera).build(
        dai.CameraBoardSocket.CAM_C, sensorFps=args.fps_limit
    )
    stereo = pipeline.create(dai.node.StereoDepth).build(
        left=left_cam.requestOutput((640, 400)),
        right=right_cam.requestOutput((640, 400)),
        presetMode=dai.node.StereoDepth.PresetMode.HIGH_DETAIL,
    )
    stereo.setDepthAlign(dai.CameraBoardSocket.CAM_A)
    if platform == "RVC2":
        stereo.setOutputSize(*nn_archive.getInputSize())
    stereo.setLeftRightCheck(True)
    stereo.setRectification(True)

    nn = pipeline.create(dai.node.SpatialDetectionNetwork).build(
        input=cam, stereo=stereo, nnArchive=nn_archive, fps=args.fps_limit
    )
    nn.setBoundingBoxScaleFactor(0.5)

    if platform == "RVC2":
        nn.setNNArchive(
            nn_archive, numShaves=6
        )  # TODO: change to numShaves=4 if running on OAK-D Lite

    img_detections_filter = pipeline.create(ImgDetectionsFilter).build(
        nn.out, labels_to_keep=[person_label]
    )

    # tracking
    tracker = pipeline.create(dai.node.ObjectTracker)
    tracker.setDetectionLabelsToTrack([person_label])  # track only person
    if platform == "RVC2":
        tracker.setTrackerType(dai.TrackerType.ZERO_TERM_COLOR_HISTOGRAM)
    else:
        tracker.setTrackerType(dai.TrackerType.SHORT_TERM_IMAGELESS)
    tracker.setTrackerIdAssignmentPolicy(dai.TrackerIdAssignmentPolicy.UNIQUE_ID)

    img_detections_filter.out.link(tracker.inputDetections)
    nn.passthrough.link(tracker.inputTrackerFrame)
    nn.passthrough.link(tracker.inputDetectionFrame)

    birds_eye_view = pipeline.create(BirdsEyeView).build(tracker.out)

    collision_avoidance = pipeline.create(CollisionAvoidanceNode).build(
        nn.passthrough, tracker.out
    )

    # visualization
    visualizer.addTopic("Video", nn.passthrough, "images")
    visualizer.addTopic("Tracklets", collision_avoidance.out, "images")
    visualizer.addTopic("Direction", collision_avoidance.out_direction, "images")
    visualizer.addTopic("Bird Frame", birds_eye_view.output, "images")
    print("Pipeline created.")

    pipeline.start()
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got q key. Exiting...")
            break
