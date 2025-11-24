from pathlib import Path

import depthai as dai
from depthai_nodes.node import (
    ParsingNeuralNetwork,
    ImgDetectionsBridge,
    ImgDetectionsFilter,
    GatherData,
)
from depthai_nodes.node.utils import generate_script_content

from utils.arguments import initialize_argparser
from utils.annotation_node import AnnotationNode

PADDING = 0.1
VALID_LABELS = [0]

_, args = initialize_argparser()

visualizer = dai.RemoteConnection(httpPort=8082)
device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()
platform = device.getPlatform().name
print(f"Platform: {platform}")

frame_type = (
    dai.ImgFrame.Type.BGR888p if platform == "RVC2" else dai.ImgFrame.Type.BGR888i
)

if args.fps_limit is None:
    args.fps_limit = 5 if platform == "RVC2" else 20
    print(
        f"\nFPS limit set to {args.fps_limit} for {platform} platform. If you want to set a custom FPS limit, use the --fps_limit flag.\n"
    )

with dai.Pipeline(device) as pipeline:
    print("Creating pipeline...")

    # detection model
    det_model_description = dai.NNModelDescription.fromYamlFile(
        f"wildlife_megadetector.{platform}.yaml"
    )
    det_nn_archive = dai.NNArchive(dai.getModelFromZoo(det_model_description))

    # pose estimation model
    pose_model_description = dai.NNModelDescription.fromYamlFile(
        f"superanimal_landmarker.{platform}.yaml"
    )
    pose_nn_archive = dai.NNArchive(dai.getModelFromZoo(pose_model_description))
    pose_model_w, pose_model_h = pose_nn_archive.getInputSize()

    # media/camera input
    if args.media_path:
        replay = pipeline.create(dai.node.ReplayVideo)
        replay.setReplayVideoFile(Path(args.media_path))
        replay.setOutFrameType(dai.ImgFrame.Type.NV12)
        replay.setLoop(True)
    else:
        cam = pipeline.create(dai.node.Camera).build()
    input_node = replay if args.media_path else cam

    detection_nn: ParsingNeuralNetwork = pipeline.create(ParsingNeuralNetwork).build(
        input_node, det_nn_archive, fps=args.fps_limit
    )

    detections_filter = pipeline.create(ImgDetectionsFilter).build(
        detection_nn.out, labels_to_keep=VALID_LABELS
    )

    # detection processing
    script = pipeline.create(dai.node.Script)
    detections_filter.out.link(script.inputs["det_in"])
    detection_nn.passthrough.link(script.inputs["preview"])
    script_content = generate_script_content(
        resize_width=pose_model_w,
        resize_height=pose_model_h,
        padding=PADDING,
        resize_mode="STRETCH",
    )
    script.setScript(script_content)

    pose_manip = pipeline.create(dai.node.ImageManip)
    pose_manip.initialConfig.setOutputSize(pose_model_w, pose_model_h)
    pose_manip.inputConfig.setWaitForMessage(True)

    script.outputs["manip_cfg"].link(pose_manip.inputConfig)
    script.outputs["manip_img"].link(pose_manip.inputImage)

    pose_nn: ParsingNeuralNetwork = pipeline.create(ParsingNeuralNetwork).build(
        pose_manip.out, pose_nn_archive
    )

    detections_bridge = pipeline.create(ImgDetectionsBridge).build(
        detections_filter.out
    )

    # detections and pose estimations sync
    gather_data = pipeline.create(GatherData).build(args.fps_limit)
    detections_bridge.out.link(gather_data.input_reference)
    pose_nn.out.link(gather_data.input_data)

    # annotation
    connection_pairs = (
        pose_nn_archive.getConfig()
        .model.heads[0]
        .metadata.extraParams["skeleton_edges"]
    )
    annotation_node = pipeline.create(AnnotationNode).build(
        input_detections=gather_data.out,
        connection_pairs=connection_pairs,
        padding=PADDING,
    )

    # visualization
    visualizer.addTopic("Video", detection_nn.passthrough, "images")
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
