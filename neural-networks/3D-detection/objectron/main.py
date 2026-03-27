from pathlib import Path

import depthai as dai
from depthai_nodes.node import (
    ParsingNeuralNetwork,
    ImgDetectionsFilter,
    GatherData,
    FrameCropper,
)

from utils.arguments import initialize_argparser
from utils.annotation_node import AnnotationNode

PADDING = 0.2
VALID_LABELS = [56]  # chair

_, args = initialize_argparser()

visualizer = dai.RemoteConnection(httpPort=8082)
device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()
platform = device.getPlatform().name
print(f"Platform: {platform}")

frame_type = (
    dai.ImgFrame.Type.BGR888p if platform == "RVC2" else dai.ImgFrame.Type.BGR888i
)

if args.fps_limit is None:
    args.fps_limit = 5 if platform == "RVC2" else 15
    print(
        f"\nFPS limit set to {args.fps_limit} for {platform} platform. If you want to set a custom FPS limit, use the --fps_limit flag.\n"
    )

with dai.Pipeline(device) as pipeline:
    print("Creating pipeline...")

    # detection model
    det_model_description = dai.NNModelDescription.fromYamlFile(
        f"yolov6_nano_r2_coco.{platform}.yaml"
    )

    # position estimation model
    pos_model_description = dai.NNModelDescription.fromYamlFile(
        f"objectron_chair.{platform}.yaml"
    )
    pos_nn_archive = dai.NNArchive(dai.getModelFromZoo(pos_model_description))
    pos_model_w, pos_model_h = pos_nn_archive.getInputSize()

    # media/camera input
    if args.media_path:
        replay = pipeline.create(dai.node.ReplayVideo)
        replay.setReplayVideoFile(Path(args.media_path))
        replay.setOutFrameType(frame_type)
        replay.setLoop(True)
    else:
        cam = pipeline.create(dai.node.Camera).build()
    input_node = replay if args.media_path else cam

    det_nn: ParsingNeuralNetwork = pipeline.create(ParsingNeuralNetwork).build(
        input_node, det_model_description, args.fps_limit
    )

    first_stage_filter = pipeline.create(ImgDetectionsFilter).build(det_nn.out)
    first_stage_filter.keepLabels(VALID_LABELS)

    # detection processing
    crop_node = (
        pipeline.create(FrameCropper)
        .fromImgDetections(
            inputImgDetections=first_stage_filter.out,
            padding=PADDING,
        )
        .build(
            inputImage=det_nn.passthrough,
            outputSize=(pos_model_w, pos_model_h),
            resizeMode=dai.ImageManipConfig.ResizeMode.STRETCH,
        )
    )

    pos_nn: ParsingNeuralNetwork = pipeline.create(ParsingNeuralNetwork).build(
        crop_node.out, pos_nn_archive
    )

    # detections and position estimations sync
    gather_data = pipeline.create(GatherData).build(
        cameraFps=args.fps_limit,
        inputData=pos_nn.getOutput(0),
        inputReference=first_stage_filter.out,
    )

    # annotation
    connection_pairs = (
        pos_nn_archive.getConfig().model.heads[0].metadata.extraParams["skeleton_edges"]
    )
    annotation_node = pipeline.create(AnnotationNode).build(
        gathered_data=gather_data.out,
        connection_pairs=connection_pairs,
        padding=PADDING,
    )

    # visualization
    visualizer.addTopic("Video", det_nn.passthrough, "images")
    visualizer.addTopic("Position", annotation_node.out_pose_annotations, "images")

    print("Pipeline created.")

    pipeline.start()
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        key_pressed = visualizer.waitKey(1)
        if key_pressed == ord("q"):
            print("Got q key. Exiting...")
            break
