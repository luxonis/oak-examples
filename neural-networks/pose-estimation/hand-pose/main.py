from pathlib import Path

import depthai as dai
from depthai_nodes.node import ParsingNeuralNetwork, GatherData

from utils.arguments import initialize_argparser
from utils.annotation_node import AnnotationNode
from utils.process import ProcessDetections

_, args = initialize_argparser()

DET_MODEL: str = "luxonis/mediapipe-palm-detection:192x192"
POSE_MODEL: str = "luxonis/mediapipe-hand-landmarker:224x224"
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
    det_model_description = dai.NNModelDescription(DET_MODEL)
    det_model_description.platform = platform
    det_nn_archive = dai.NNArchive(dai.getModelFromZoo(det_model_description))

    # pose estimation model
    pose_model_description = dai.NNModelDescription(POSE_MODEL)
    pose_model_description.platform = platform
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

    script = pipeline.create(dai.node.Script)
    script.setScriptPath(str(Path(__file__).parent / "utils/script.py"))
    script.inputs["frame_input"].setMaxSize(30)
    script.inputs["config_input"].setMaxSize(30)
    script.inputs["num_configs_input"].setMaxSize(30)

    detection_nn.passthrough.link(script.inputs["frame_input"])
    detections_processor.config_output.link(script.inputs["config_input"])
    detections_processor.num_configs_output.link(script.inputs["num_configs_input"])

    pose_manip = pipeline.create(dai.node.ImageManip)
    pose_manip.initialConfig.setOutputSize(
        pose_nn_archive.getInputWidth(), pose_nn_archive.getInputHeight()
    )
    pose_manip.inputConfig.setMaxSize(30)
    pose_manip.inputImage.setMaxSize(30)
    pose_manip.setNumFramesPool(30)
    pose_manip.inputConfig.setWaitForMessage(True)

    script.outputs["output_config"].link(pose_manip.inputConfig)
    script.outputs["output_frame"].link(pose_manip.inputImage)

    pose_nn: ParsingNeuralNetwork = pipeline.create(ParsingNeuralNetwork).build(
        pose_manip.out, pose_nn_archive
    )

    # detections and pose estimations sync
    gather_data = pipeline.create(GatherData).build(camera_fps=args.fps_limit)
    detection_nn.out.link(gather_data.input_reference)
    pose_nn.outputs.link(gather_data.input_data)

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

    # visualization
    visualizer.addTopic("Video", input_node, "images")
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
