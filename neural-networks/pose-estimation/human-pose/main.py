from pathlib import Path

import depthai as dai
from depthai_nodes.node import (
    ParsingNeuralNetwork,
    HRNetParser,
    GatherData,
    ImgDetectionsFilter,
)
from depthai_nodes.node.utils import generate_script_content

from utils.arguments import initialize_argparser
from utils.annotation_node import AnnotationNode

PADDING = 0.1

_, args = initialize_argparser()

visualizer = dai.RemoteConnection(httpPort=8082)
device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()
platform = device.getPlatform().name
print(f"Platform: {platform}")

frame_type = (
    dai.ImgFrame.Type.BGR888i if platform == "RVC4" else dai.ImgFrame.Type.BGR888p
)

if not args.fps_limit:
    args.fps_limit = 5 if platform == "RVC2" else 30
    print(
        f"\nFPS limit set to {args.fps_limit} for {platform} platform. If you want to set a custom FPS limit, use the --fps_limit flag.\n"
    )

with dai.Pipeline(device) as pipeline:
    print("Creating pipeline...")

    # person detection model
    det_model_description = dai.NNModelDescription.fromYamlFile(
        f"yolov6_nano_r2_coco.{platform}.yaml"
    )
    det_model_nn_archive = dai.NNArchive(dai.getModelFromZoo(det_model_description))

    # pose estimation model
    rec_model_description = dai.NNModelDescription.fromYamlFile(
        f"lite_hrnet_18coco.{platform}.yaml"
    )
    if rec_model_description.model != args.model:
        rec_model_description = dai.NNModelDescription(args.model, platform=platform)
    rec_model_nn_archive = dai.NNArchive(dai.getModelFromZoo(rec_model_description))

    # media/camera source
    if args.media_path:
        replay = pipeline.create(dai.node.ReplayVideo)
        replay.setReplayVideoFile(Path(args.media_path))
        replay.setOutFrameType(frame_type)
        replay.setLoop(True)
    else:
        cam = pipeline.create(dai.node.Camera).build()
    input_node = replay if args.media_path else cam

    det_nn: ParsingNeuralNetwork = pipeline.create(ParsingNeuralNetwork).build(
        input_node, det_model_nn_archive, fps=args.fps_limit
    )
    det_nn.input.setBlocking(False)
    det_nn.input.setMaxSize(1)

    # detection processing
    valid_labels = [
        det_model_nn_archive.getConfig().model.heads[0].metadata.classes.index("person")
    ]
    detections_filter = pipeline.create(ImgDetectionsFilter).build(
        det_nn.out, labels_to_keep=valid_labels
    )  # we only want to work with person detections

    script_node = pipeline.create(dai.node.Script)
    det_nn.out.link(script_node.inputs["det_in"])
    det_nn.passthrough.link(script_node.inputs["preview"])
    script_content = generate_script_content(
        resize_width=rec_model_nn_archive.getInputWidth(),
        resize_height=rec_model_nn_archive.getInputHeight(),
        padding=PADDING,
    )
    script_node.setScript(script_content)

    crop_node = pipeline.create(dai.node.ImageManip)
    crop_node.initialConfig.setOutputSize(
        rec_model_nn_archive.getInputWidth(), rec_model_nn_archive.getInputHeight()
    )
    crop_node.inputConfig.setWaitForMessage(True)

    script_node.outputs["manip_cfg"].link(crop_node.inputConfig)
    script_node.outputs["manip_img"].link(crop_node.inputImage)

    rec_nn: ParsingNeuralNetwork = pipeline.create(ParsingNeuralNetwork).build(
        crop_node.out, rec_model_nn_archive
    )
    rec_nn.input.setBlocking(False)
    rec_nn.input.setMaxSize(1)
    parser: HRNetParser = rec_nn.getParser(0)
    parser.setScoreThreshold(
        0.0
    )  # to get all keypoints so we can draw skeleton. We will filter them later.

    # detections and recognitions sync
    gather_data_node = pipeline.create(GatherData).build(args.fps_limit)
    rec_nn.out.link(gather_data_node.input_data)
    detections_filter.out.link(gather_data_node.input_reference)

    # annotation
    skeleton_edges = (
        rec_model_nn_archive.getConfig()
        .model.heads[0]
        .metadata.extraParams["skeleton_edges"]
    )
    annotation_node = pipeline.create(AnnotationNode).build(
        gather_data_node.out,
        connection_pairs=skeleton_edges,
        valid_labels=valid_labels,
    )

    # visualization
    visualizer.addTopic("Video", det_nn.passthrough, "images")
    visualizer.addTopic("Detections", detections_filter.out, "images")
    visualizer.addTopic("Pose", annotation_node.out_pose_annotations, "images")

    print("Pipeline created.")

    pipeline.start()
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got q key. Exiting...")
            break
