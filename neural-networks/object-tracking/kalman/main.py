import depthai as dai

from utils.kalman_filter_node import KalmanFilterNode
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
    nn.setBoundingBoxScaleFactor(0.7)
    nn.setDepthLowerThreshold(100)
    nn.setDepthUpperThreshold(5000)
    if platform == "RVC2":
        nn.setNNArchive(
            nn_archive, numShaves=6
        )  # TODO: change to numShaves=4 if running on OAK-D Lite

    # tracking
    object_tracker = pipeline.create(dai.node.ObjectTracker)
    object_tracker.setDetectionLabelsToTrack([person_label])  # track only person
    if platform == "RVC2":
        object_tracker.setTrackerType(dai.TrackerType.ZERO_TERM_COLOR_HISTOGRAM)
    else:
        object_tracker.setTrackerType(dai.TrackerType.SHORT_TERM_IMAGELESS)
    object_tracker.setTrackerIdAssignmentPolicy(dai.TrackerIdAssignmentPolicy.UNIQUE_ID)

    nn.passthrough.link(object_tracker.inputTrackerFrame)
    nn.passthrough.link(object_tracker.inputDetectionFrame)
    nn.out.link(object_tracker.inputDetections)

    calibration_handler = device.readCalibration()
    baseline = calibration_handler.getBaselineDistance() * 10
    focal_length = calibration_handler.getCameraIntrinsics(
        dai.CameraBoardSocket.CAM_C, 640, 400
    )[0][0]

    # kalman filter
    kalman_filter_node = pipeline.create(KalmanFilterNode).build(
        rgb=nn.passthrough,
        tracker_out=object_tracker.out,
        baseline=baseline,
        focal_length=focal_length,
        label_map=labels,
    )

    # visualization
    visualizer.addTopic("Video", nn.passthrough, "images")
    visualizer.addTopic("Tracklets", kalman_filter_node.out, "images")

    print("Pipeline created.")

    pipeline.start()
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got q key. Exiting...")
            break
