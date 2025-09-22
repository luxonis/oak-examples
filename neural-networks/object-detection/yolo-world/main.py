from pathlib import Path

import depthai as dai
from depthai_nodes.node import (
    ParsingNeuralNetwork,
    ImgDetectionsFilter,
)

from utils.helper_functions import extract_text_embeddings
from utils.arguments import initialize_argparser
from utils.annotation_node import AnnotationNode

MAX_NUM_CLASSES = 80

_, args = initialize_argparser()

visualizer = dai.RemoteConnection(httpPort=8082)
device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()
platform = device.getPlatformAsString()
print(f"Platform: {platform}")

frame_type = (
    dai.ImgFrame.Type.BGR888i if platform == "RVC4" else dai.ImgFrame.Type.BGR888p
)

text_features = extract_text_embeddings(
    class_names=args.class_names, max_num_classes=MAX_NUM_CLASSES
)

if len(args.class_names) > MAX_NUM_CLASSES:
    raise ValueError(
        f"Number of classes exceeds the maximum number of classes: {MAX_NUM_CLASSES}"
    )

if args.fps_limit is None:
    args.fps_limit = 30
    print(
        f"\nFPS limit set to {args.fps_limit} for {platform} platform. If you want to set a custom FPS limit, use the --fps_limit flag.\n"
    )

with dai.Pipeline(device) as pipeline:
    print("Creating pipeline...")

    # yolo world model
    model_description = dai.NNModelDescription.fromYamlFile(
        f"yolo_world_l.{platform}.yaml"
    )
    model_nn_archive = dai.NNArchive(dai.getModelFromZoo(model_description))
    model_w, model_h = model_nn_archive.getInputSize()

    # media/camera input
    if args.media_path:
        replay = pipeline.create(dai.node.ReplayVideo)
        replay.setReplayVideoFile(Path(args.media_path))
        replay.setOutFrameType(frame_type)
        replay.setLoop(True)
        if args.fps_limit:
            replay.setFps(args.fps_limit)
        replay.setSize(model_w, model_h)
    else:
        cam = pipeline.create(dai.node.Camera).build(
            boardSocket=dai.CameraBoardSocket.CAM_A
        )
        cam_out = cam.requestOutput(
            size=(model_w, model_h), type=frame_type, fps=args.fps_limit
        )
    input_node = replay.out if args.media_path else cam_out

    nn_with_parser = pipeline.create(ParsingNeuralNetwork)
    nn_with_parser.setNNArchive(model_nn_archive)
    nn_with_parser.setBackend("snpe")
    nn_with_parser.setBackendProperties(
        {"runtime": "dsp", "performance_profile": "default"}
    )
    nn_with_parser.setNumInferenceThreads(1)
    nn_with_parser.getParser(0).setConfidenceThreshold(args.confidence_thresh)

    input_node.link(nn_with_parser.inputs["images"])

    textInputQueue = nn_with_parser.inputs["texts"].createInputQueue()
    nn_with_parser.inputs["texts"].setReusePreviousMessage(True)

    # filter and rename detection labels
    det_process_filter = pipeline.create(ImgDetectionsFilter).build(nn_with_parser.out)
    det_process_filter.setLabels(
        labels=[i for i in range(len(args.class_names))], keep=True
    )
    annotation_node = pipeline.create(AnnotationNode).build(
        det_process_filter.out,
        label_encoding={k: v for k, v in enumerate(args.class_names)},
    )

    # visualization
    visualizer.addTopic("Detections", annotation_node.out)
    visualizer.addTopic("Video", nn_with_parser.passthroughs["images"])

    print("Pipeline created.")

    pipeline.start()
    visualizer.registerPipeline(pipeline)

    inputNNData = dai.NNData()
    inputNNData.addTensor("texts", text_features, dataType=dai.TensorInfo.DataType.U8F)
    textInputQueue.send(inputNNData)

    print("Press 'q' to stop")

    while pipeline.isRunning():
        pipeline.processTasks()
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got q key. Exiting...")
            break
