from pathlib import Path

import depthai as dai
from depthai_nodes.node import ParsingNeuralNetwork, GatherData, FrameCropper

from utils.annotation_node import AnnotationNode
from utils.arguments import initialize_argparser

REQ_WIDTH, REQ_HEIGHT = (
    1024,
    768,
)  # we are requesting larger input size than required because we want to keep some resolution for the second stage model

_, args = initialize_argparser()

visualizer = dai.RemoteConnection(httpPort=8082)
device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()
platform = device.getPlatform().name
print(f"Platform: {platform}")

frame_type = (
    dai.ImgFrame.Type.BGR888p if platform == "RVC2" else dai.ImgFrame.Type.BGR888i
)

if args.fps_limit is None:
    args.fps_limit = 14 if platform == "RVC2" else 30
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
    det_model_w, det_model_h = det_model_nn_archive.getInputSize()

    # head pose estimation model
    pose_model_description = dai.NNModelDescription.fromYamlFile(
        f"head_pose_estimation.{platform}.yaml"
    )
    pose_model_nn_archive = dai.NNArchive(dai.getModelFromZoo(pose_model_description))
    pose_model_w, pose_model_h = pose_model_nn_archive.getInputSize()

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
    resize_node.initialConfig.setOutputSize(det_model_w, det_model_h)
    resize_node.initialConfig.setReusePreviousImage(False)
    resize_node.inputImage.setBlocking(True)
    input_node_out.link(resize_node.inputImage)

    det_nn: ParsingNeuralNetwork = pipeline.create(ParsingNeuralNetwork).build(
        resize_node.out, det_model_nn_archive
    )
    det_nn.input.setBlocking(True)

    crop_node = pipeline.create(FrameCropper).fromImgDetections(
        inputImgDetections=det_nn.out,
    ).build(
        inputImage=input_node_out,
        outputSize=(pose_model_w, pose_model_h),
    )

    pose_nn: ParsingNeuralNetwork = pipeline.create(ParsingNeuralNetwork).build(
        crop_node.out, pose_model_nn_archive
    )

    # detections and recognitions sync
    gather_data_node = pipeline.create(GatherData).build(
        camera_fps=args.fps_limit,
        input_data=pose_nn.outputs,
        input_reference=det_nn.out,
    )

    # annotation
    annotation_node = pipeline.create(AnnotationNode).build(gather_data_node.out)

    # visualization
    visualizer.addTopic("Video", det_nn.passthrough, "images")
    visualizer.addTopic("Detections", det_nn.out, "images")
    visualizer.addTopic("Pose", annotation_node.out, "images")

    print("Pipeline created.")
    pipeline.start()
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got q key. Exiting...")
            break
