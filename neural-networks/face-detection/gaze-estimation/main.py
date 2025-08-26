from pathlib import Path

import depthai as dai
from depthai_nodes.node import ParsingNeuralNetwork, GatherData

from utils.arguments import initialize_argparser
from utils.process_keypoints import LandmarksProcessing
from utils.node_creators import create_crop_node
from utils.annotation_node import AnnotationNode
from utils.host_concatenate_head_pose import ConcatenateHeadPose

REQ_WIDTH, REQ_HEIGHT = (
    640,
    480,
)  # we are requesting larger input size than required because we want to keep some resolution for the second stage model

_, args = initialize_argparser()

visualizer = dai.RemoteConnection(httpPort=8082)
device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()
platform = device.getPlatform().name
print(f"Platform: {platform}")

if platform == "RVC4":
    REQ_WIDTH, REQ_HEIGHT = (768, 768)

frame_type = (
    dai.ImgFrame.Type.BGR888i if platform == "RVC4" else dai.ImgFrame.Type.BGR888p
)

if args.fps_limit is None:
    args.fps_limit = 15 if platform == "RVC2" else 30
    print(
        f"\nFPS limit set to {args.fps_limit} for {platform} platform. If you want to set a custom FPS limit, use the --fps_limit flag.\n"
    )

with dai.Pipeline(device) as pipeline:
    print("Creating pipeline...")

    # face detection model
    det_model_description = dai.NNModelDescription.fromYamlFile(
        f"yunet.{platform}.yaml"
    )
    det_model_nn_archive = dai.NNArchive(dai.getModelFromZoo(det_model_description))

    # head pose model
    head_pose_model_description = dai.NNModelDescription.fromYamlFile(
        f"head_pose_estimation.{platform}.yaml"
    )
    head_pose_model_description.platform = platform
    head_pose_model_nn_archive = dai.NNArchive(
        dai.getModelFromZoo(head_pose_model_description)
    )

    # gaze estimation model
    gaze_model_description = dai.NNModelDescription.fromYamlFile(
        f"gaze_estimation_adas.{platform}.yaml"
    )
    gaze_model_description.platform = platform
    gaze_model_nn_archive = dai.NNArchive(dai.getModelFromZoo(gaze_model_description))

    # media/camera input
    if args.media_path:
        replay = pipeline.create(dai.node.ReplayVideo)
        replay.setReplayVideoFile(Path(args.media_path))
        replay.setOutFrameType(frame_type)
        replay.setLoop(True)
        if args.fps_limit:
            replay.setFps(args.fps_limit)
        replay.setSize(REQ_WIDTH, REQ_HEIGHT)
    else:
        cam = pipeline.create(dai.node.Camera).build()
        cam_out = cam.requestOutput(
            size=(REQ_WIDTH, REQ_HEIGHT), type=frame_type, fps=args.fps_limit
        )
    input_node_out = replay.out if args.media_path else cam_out

    # resize to det model input size
    resize_node = pipeline.create(dai.node.ImageManip)
    resize_node.initialConfig.setOutputSize(
        det_model_nn_archive.getInputWidth(), det_model_nn_archive.getInputHeight()
    )
    resize_node.setMaxOutputFrameSize(
        det_model_nn_archive.getInputWidth() * det_model_nn_archive.getInputHeight() * 3
    )
    resize_node.initialConfig.setReusePreviousImage(False)
    resize_node.inputImage.setBlocking(True)
    input_node_out.link(resize_node.inputImage)

    det_nn: ParsingNeuralNetwork = pipeline.create(ParsingNeuralNetwork).build(
        resize_node.out, det_model_nn_archive
    )
    det_nn.input.setBlocking(True)

    # detection processing
    detection_process_node = pipeline.create(LandmarksProcessing)
    detection_process_node.set_source_size(REQ_WIDTH, REQ_HEIGHT)
    detection_process_node.set_target_size(
        head_pose_model_nn_archive.getInputWidth(),
        head_pose_model_nn_archive.getInputHeight(),
    )
    det_nn.out.link(detection_process_node.detections_input)

    left_eye_crop_node = create_crop_node(
        pipeline, input_node_out, detection_process_node.left_config_output
    )
    right_eye_crop_node = create_crop_node(
        pipeline, input_node_out, detection_process_node.right_config_output
    )
    face_crop_node = create_crop_node(
        pipeline, input_node_out, detection_process_node.face_config_output
    )

    # head pose estimation
    head_pose_nn = pipeline.create(ParsingNeuralNetwork).build(
        face_crop_node.out, head_pose_model_nn_archive
    )
    head_pose_nn.input.setBlocking(True)

    head_pose_concatenate_node = pipeline.create(ConcatenateHeadPose).build(
        head_pose_nn.getOutput(0), head_pose_nn.getOutput(1), head_pose_nn.getOutput(2)
    )

    # gaze estimation
    gaze_estimation_node = pipeline.create(dai.node.NeuralNetwork)
    gaze_estimation_node.setNNArchive(gaze_model_nn_archive)
    head_pose_concatenate_node.output.link(
        gaze_estimation_node.inputs["head_pose_angles_yaw_pitch_roll"]
    )
    left_eye_crop_node.out.link(gaze_estimation_node.inputs["left_eye_image"])
    right_eye_crop_node.out.link(gaze_estimation_node.inputs["right_eye_image"])
    gaze_estimation_node.inputs["head_pose_angles_yaw_pitch_roll"].setBlocking(True)
    gaze_estimation_node.inputs["left_eye_image"].setBlocking(True)
    gaze_estimation_node.inputs["right_eye_image"].setBlocking(True)
    gaze_estimation_node.inputs["left_eye_image"].setMaxSize(5)
    gaze_estimation_node.inputs["right_eye_image"].setMaxSize(5)
    gaze_estimation_node.inputs["head_pose_angles_yaw_pitch_roll"].setMaxSize(5)

    # detections and gaze estimations sync
    gather_data_node = pipeline.create(GatherData).build(args.fps_limit)
    gaze_estimation_node.out.link(gather_data_node.input_data)
    det_nn.out.link(gather_data_node.input_reference)

    # annotation
    annotation_node = pipeline.create(AnnotationNode).build(gather_data_node.out)

    # visualization
    visualizer.addTopic("Video", input_node_out, "images")
    visualizer.addTopic("Gaze", annotation_node.out, "images")

    print("Pipeline created.")

    pipeline.start()
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got q key. Exiting...")
            break
