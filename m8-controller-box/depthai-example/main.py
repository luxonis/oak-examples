"""
Controller Box DepthAI Hand Detection Example
---------------------------------------------

This example demonstrates integration of the ControllerBox
with a DepthAI hand detection pipeline.

- Runs hand detection using DepthAI
- Turns ON LED 1 when a hand is detected
- Turns OFF LED 1 when no hand is present

This showcases how to combine AI perception with hardware control.
"""

from pathlib import Path
import time

import depthai as dai
from depthai_nodes.node import ParsingNeuralNetwork, GatherData

from utils.arguments import initialize_argparser
from utils.annotation_node import AnnotationNode
from utils.process import ProcessDetections

# Controller Box
from luxonis_u2if import ControllerBox


# ------------------------------------------------------------
# Connect to ControllerBox device
# ------------------------------------------------------------

box = ControllerBox()
box.led_init()


# ------------------------------------------------------------
# Configuration
# ------------------------------------------------------------

_, args = initialize_argparser()

PADDING = 0.1
CONFIDENCE_THRESHOLD = 0.5


# ------------------------------------------------------------
# Device setup
# ------------------------------------------------------------

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
        f"\nFPS limit set to {args.fps_limit} for {platform} platform.\n"
    )


# ------------------------------------------------------------
# Pipeline
# ------------------------------------------------------------

with dai.Pipeline(device) as pipeline:
    print("Creating pipeline...")

    # Detection model
    det_model_description = dai.NNModelDescription.fromYamlFile(
        f"mediapipe_palm_detection.{platform}.yaml"
    )
    det_nn_archive = dai.NNArchive(dai.getModelFromZoo(det_model_description))

    # Pose model
    pose_model_description = dai.NNModelDescription.fromYamlFile(
        f"mediapipe_hand_landmarker.{platform}.yaml"
    )
    pose_nn_archive = dai.NNArchive(dai.getModelFromZoo(pose_model_description))

    # Input source
    if args.media_path:
        replay = pipeline.create(dai.node.ReplayVideo)
        replay.setReplayVideoFile(Path(args.media_path))
        replay.setOutFrameType(frame_type)
        replay.setLoop(True)
        if args.fps_limit:
            replay.setFps(args.fps_limit)
        input_node = replay.out
    else:
        cam = pipeline.create(dai.node.Camera).build()
        cam_out = cam.requestOutput((768, 768), frame_type, fps=args.fps_limit)
        input_node = cam_out

    # Resize for detection
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

    # Detection processing
    detections_processor = pipeline.create(ProcessDetections).build(
        detections_input=detection_nn.out,
        padding=PADDING,
        target_size=(pose_nn_archive.getInputWidth(), pose_nn_archive.getInputHeight()),
    )

    # Script node
    script = pipeline.create(dai.node.Script)
    script.setScriptPath(str(Path(__file__).parent / "utils/script.py"))

    detection_nn.passthrough.link(script.inputs["frame_input"])
    detections_processor.config_output.link(script.inputs["config_input"])
    detections_processor.num_configs_output.link(script.inputs["num_configs_input"])

    # Pose manipulation
    pose_manip = pipeline.create(dai.node.ImageManip)
    pose_manip.initialConfig.setOutputSize(
        pose_nn_archive.getInputWidth(),
        pose_nn_archive.getInputHeight(),
    )

    script.outputs["output_config"].link(pose_manip.inputConfig)
    script.outputs["output_frame"].link(pose_manip.inputImage)

    pose_nn: ParsingNeuralNetwork = pipeline.create(ParsingNeuralNetwork).build(
        pose_manip.out, pose_nn_archive
    )

    # Sync detections + pose
    gather_data = pipeline.create(GatherData).build(camera_fps=args.fps_limit)
    detection_nn.out.link(gather_data.input_reference)
    pose_nn.outputs.link(gather_data.input_data)

    # Annotation
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

    # Video encoding
    video_encode_manip = pipeline.create(dai.node.ImageManip)
    video_encode_manip.initialConfig.setOutputSize(768, 768)
    video_encode_manip.initialConfig.setFrameType(dai.ImgFrame.Type.NV12)
    input_node.link(video_encode_manip.inputImage)

    video_encoder = pipeline.create(dai.node.VideoEncoder)
    video_encoder.setDefaultProfilePreset(
        args.fps_limit, dai.VideoEncoderProperties.Profile.H264_MAIN
    )
    video_encode_manip.out.link(video_encoder.input)

    # Visualization
    visualizer.addTopic("Video", video_encoder.out, "images")
    visualizer.addTopic("Detections", annotation_node.out_detections, "images")
    visualizer.addTopic("Pose", annotation_node.out_pose_annotations, "images")

    print("Pipeline created.")

    # Output queue
    det_queue = detection_nn.out.createOutputQueue(maxSize=4, blocking=False)

    pipeline.start()
    visualizer.registerPipeline(pipeline)


    # ------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------

    while pipeline.isRunning():
        det_in = det_queue.tryGet()

        if det_in is not None:
            detections = det_in.detections if hasattr(det_in, "detections") else []

            if len(detections) > 0:
                box.led_on(1)
            else:
                box.led_off(1)

        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got q key. Exiting...")
            break