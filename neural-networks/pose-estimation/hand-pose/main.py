from pathlib import Path

import depthai as dai
from depthai_nodes.node import ParsingNeuralNetwork, GatherData, FrameCropper

from utils.arguments import initialize_argparser
from utils.annotation_node import AnnotationNode
from utils.process import ProcessDetections

_, args = initialize_argparser()

PADDING = 0.1
CONFIDENCE_THRESHOLD = 0.5

visualizer = dai.RemoteConnection(httpPort=8082)
device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()
platform = device.getPlatform().name
print(f"Platform: {platform}")

frame_type = (
    dai.ImgFrame.Type.BGR888p if platform == "RVC2" else dai.ImgFrame.Type.BGR888i
)

if not args.fps_limit:
    args.fps_limit = 8 if platform == "RVC2" else 30
    print(
        f"\nFPS limit set to {args.fps_limit} for {platform} platform. If you want to set a custom FPS limit, use the --fps_limit flag.\n"
    )

with dai.Pipeline(device) as pipeline:
    print("Creating pipeline...")

    # detection model
    det_model_description = dai.NNModelDescription.fromYamlFile(
        f"mediapipe_palm_detection.{platform}.yaml"
    )
    det_nn_archive = dai.NNArchive(dai.getModelFromZoo(det_model_description))

    # pose estimation model
    pose_model_description = dai.NNModelDescription.fromYamlFile(
        f"mediapipe_hand_landmarker.{platform}.yaml"
    )
    pose_nn_archive = dai.NNArchive(dai.getModelFromZoo(pose_model_description))

    # media/camera input
    if args.media_path:
        replay = pipeline.create(dai.node.ReplayVideo)
        replay.setReplayVideoFile(Path(args.media_path))
        replay.setOutFrameType(frame_type)
        replay.setLoop(True)
        if args.fps_limit:
            replay.setFps(args.fps_limit)
    else:
        cam = pipeline.create(dai.node.Camera).build()
        cam_out = cam.requestOutput((768, 768), frame_type, fps=args.fps_limit)
    input_node = replay.out if args.media_path else cam_out

    # resize to det model input size
    resize_node = pipeline.create(dai.node.ImageManip)
    resize_node.setMaxOutputFrameSize(
        det_nn_archive.getInputWidth() * det_nn_archive.getInputHeight() * 3
    )
    resize_node.initialConfig.setOutputSize(
        det_nn_archive.getInputWidth(),
        det_nn_archive.getInputHeight(),
        mode=dai.ImageManipConfig.ResizeMode.STRETCH,
    )
    resize_node.initialConfig.setFrameType(frame_type)
    input_node.link(resize_node.inputImage)

    detection_nn: ParsingNeuralNetwork = pipeline.create(ParsingNeuralNetwork).build(
        resize_node.out, det_nn_archive
    )

    # detection processing
    detections_processor = pipeline.create(ProcessDetections).build(
        detections_input=detection_nn.out,
        padding=PADDING,
        target_size=(pose_nn_archive.getInputWidth(), pose_nn_archive.getInputHeight()),
    )

    # hand crop + pose estimation
    crop_output_size = (
        pose_nn_archive.getInputWidth(),
        pose_nn_archive.getInputHeight(),
    )
    hand_crop_node = (
        pipeline.create(FrameCropper)
        .fromManipConfigs(
            inputManipConfigs=detections_processor.config_output,
            maxOutputFrameSize=crop_output_size[0] * crop_output_size[1] * 3,
            waitForConfig=True,
        )
        .build(detection_nn.passthrough)
    )

    pose_nn: ParsingNeuralNetwork = pipeline.create(ParsingNeuralNetwork).build(
        hand_crop_node.out, pose_nn_archive
    )

    # detections and pose estimations sync
    gather_data = pipeline.create(GatherData).build(
        cameraFps=args.fps_limit,
        inputData=pose_nn.outputs,
        inputReference=detection_nn.out,
    )

    # annotation
    connection_pairs = (
        pose_nn_archive.getConfig()
        .model.heads[0]
        .metadata.extraParams["skeleton_edges"]
    )
    annotation_node = pipeline.create(AnnotationNode).build(
        gathered_data=gather_data.out,
        video=input_node,
        padding_factor=PADDING,
        confidence_threshold=CONFIDENCE_THRESHOLD,
        connections_pairs=connection_pairs,
    )

    # video encoding
    video_encode_manip = pipeline.create(dai.node.ImageManip)
    video_encode_manip.setMaxOutputFrameSize(768 * 768 * 3)
    video_encode_manip.initialConfig.setOutputSize(768, 768)
    video_encode_manip.initialConfig.setFrameType(dai.ImgFrame.Type.NV12)
    input_node.link(video_encode_manip.inputImage)

    video_encoder = pipeline.create(dai.node.VideoEncoder)
    video_encoder.setMaxOutputFrameSize(768 * 768 * 3)
    video_encoder.setDefaultProfilePreset(
        args.fps_limit, dai.VideoEncoderProperties.Profile.H264_MAIN
    )
    video_encode_manip.out.link(video_encoder.input)

    # visualization
    visualizer.addTopic("Video", video_encoder.out, "images")
    visualizer.addTopic("Detections", annotation_node.out_detections, "images")
    visualizer.addTopic("Pose", annotation_node.out_pose_annotations, "images")

    print("Pipeline created.")

    pipeline.start()
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got q key. Exiting...")
            break
