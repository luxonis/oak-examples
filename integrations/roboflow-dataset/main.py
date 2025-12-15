from pathlib import Path

import depthai as dai
from depthai_nodes.node.parsing_neural_network import ParsingNeuralNetwork
from utils.arguments import initialize_argparser
from utils.roboflow_node import RoboflowNode
from utils.roboflow_uploader import RoboflowUploader

_, args = initialize_argparser()

visualizer = dai.RemoteConnection(httpPort=8082)
device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()

with dai.Pipeline(device) as pipeline:
    print("Creating pipeline...")

    platform = device.getPlatform()
    model_description = dai.NNModelDescription.fromYamlFile(
        f"yolov6_nano_r2_coco.{platform.name}.yaml"
    )
    nn_archive = dai.NNArchive(dai.getModelFromZoo(model_description))

    if args.media_path:
        replay = pipeline.create(dai.node.ReplayVideo)
        replay.setReplayVideoFile(Path(args.media_path))
        replay.setOutFrameType(
            dai.ImgFrame.Type.BGR888i
            if platform == dai.Platform.RVC4
            else dai.ImgFrame.Type.BGR888p
        )
        replay.setLoop(True)
        if args.fps_limit:
            replay.setFps(args.fps_limit)
            args.fps_limit = None  # only want to set it once
        replay.setSize(nn_archive.getInputWidth(), nn_archive.getInputHeight())

    input_node = replay if args.media_path else pipeline.create(dai.node.Camera).build()

    nn_with_parser = pipeline.create(ParsingNeuralNetwork).build(
        input_node, nn_archive, fps=args.fps_limit
    )

    uploader = RoboflowUploader(
        api_key=args.api_key, workspace_name=args.workspace, dataset_name=args.dataset
    )

    roboflow = pipeline.create(RoboflowNode).build(
        preview=nn_with_parser.passthrough,
        nn=nn_with_parser.out,
        uploader=uploader,
        auto_interval=args.auto_interval,
        auto_threshold=args.auto_threshold,
        labels=nn_archive.getConfigV1().model.heads[0].metadata.classes,
    )

    visualizer.addTopic("Video", nn_with_parser.passthrough, "images")
    visualizer.addTopic("Detections", nn_with_parser.out, "images")

    print("Pipeline created.")

    pipeline.start()
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        key = visualizer.waitKey(1)
        pipeline.processTasks()
        if key == ord("q"):
            print("Got q key from the remote connection!")
            break
        else:
            roboflow.handle_key(key)
