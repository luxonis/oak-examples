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
    det_model_archive = dai.NNArchive(dai.getModelFromZoo(det_model_description))

    # media/camera input
    if args.media_path:
        replay = pipeline.create(dai.node.ReplayVideo)
        replay.setReplayVideoFile(Path(args.media_path))
        replay.setOutFrameType(dai.ImgFrame.Type.NV12)
        replay.setSize(1920, 1080)
        replay.setFps(args.fps_limit)
        replay.setLoop(True)
        nn_input = pipeline.create(dai.node.ImageManip)
        nn_input.setMaxOutputFrameSize(
            det_model_archive.getInputWidth() * det_model_archive.getInputHeight() * 3
        )
        nn_input.initialConfig.setOutputSize(
            det_model_archive.getInputWidth(), det_model_archive.getInputHeight()
        )
        nn_input.initialConfig.setFrameType(frame_type)
        replay.out.link(nn_input.inputImage)
    else:
        cam = pipeline.create(dai.node.Camera).build()
    input_node = nn_input.out if args.media_path else cam

    nn: ParsingNeuralNetwork = pipeline.create(ParsingNeuralNetwork).build(
        input_node, det_model_archive, None if args.media_path else args.fps_limit
    )
    nn.setNumInferenceThreads(2)
    nn.input.setBlocking(False)

    video = (
        replay.out
        if args.media_path
        else cam.requestOutput((1920, 1080), dai.ImgFrame.Type.NV12, fps=args.fps_limit)
    )
    video_encoder = pipeline.create(dai.node.VideoEncoder).build(
        video,
        frameRate=args.fps_limit,
        profile=dai.VideoEncoderProperties.Profile.H264_MAIN,
    )

    # object tracking
    objectTracker = pipeline.create(dai.node.ObjectTracker)
    if platform == "RVC2":
        objectTracker.setTrackerType(dai.TrackerType.ZERO_TERM_COLOR_HISTOGRAM)
    else:
        objectTracker.setTrackerType(dai.TrackerType.SHORT_TERM_IMAGELESS)

    objectTracker.setTrackerIdAssignmentPolicy(
        dai.TrackerIdAssignmentPolicy.SMALLEST_ID
    )
    if args.track_labels is not None:
        objectTracker.setDetectionLabelsToTrack(args.track_labels)
    nn.passthrough.link(objectTracker.inputTrackerFrame)
    nn.passthrough.link(objectTracker.inputDetectionFrame)
    nn.out.link(objectTracker.inputDetections)

    # annotation
    annotation_node = pipeline.create(AnnotationNode).build(
        objectTracker.out,
        axis=args.axis,
        roi_position=args.roi_position,
        crossing_margin=args.crossing_margin,
    )

    # visualization
    visualizer.addTopic("Video", video_encoder.out, "images")
    if args.show_raw_detections:
        visualizer.addTopic("Detections", nn.out, "images")
    visualizer.addTopic("Count", annotation_node.out, "images")

    print("Pipeline created.")
    pipeline.start()
    print("Pipeline started.")
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        key_pressed = visualizer.waitKey(1)
        if key_pressed == ord("q"):
            print("Got q key. Exiting...")
            break
