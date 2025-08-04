from pathlib import Path

import depthai as dai
from depthai_nodes.node import (
    ParsingNeuralNetwork,
    ImgDetectionsFilter,
)

from utils.helper_functions import (
    extract_text_embeddings,
    extract_image_prompt_embeddings,
    base64_to_cv2_image,
)
from utils.arguments import initialize_argparser
from utils.annotation_node import AnnotationNode

_, args = initialize_argparser()

IP = args.ip or "localhost"
PORT = args.port or 8080

CLASS_NAMES = ["person", "chair", "TV"]
MAX_NUM_CLASSES = 80
CONFIDENCE_THRESHOLD = 0.1

visualizer = dai.RemoteConnection(serveFrontend=False)
device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()
platform = device.getPlatformAsString()

if platform != "RVC4":
    raise ValueError("This example is supported only on RVC4 platform")

frame_type = dai.ImgFrame.Type.BGR888i
text_features = extract_text_embeddings(
    class_names=CLASS_NAMES, max_num_classes=MAX_NUM_CLASSES
)

if args.fps_limit is None:
    args.fps_limit = 5
    print(
        f"\nFPS limit set to {args.fps_limit} for {platform} platform. If you want to set a custom FPS limit, use the --fps_limit flag.\n"
    )

with dai.Pipeline(device) as pipeline:
    print("Creating pipeline...")

    # yolo world model
    model_description = dai.NNModelDescription.fromYamlFile(
        f"yolo_world_l.{platform}.yaml"
    )
    model_description.platform = platform
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
    nn_with_parser.getParser(0).setConfidenceThreshold(CONFIDENCE_THRESHOLD)

    input_node.link(nn_with_parser.inputs["images"])

    textInputQueue = nn_with_parser.inputs["texts"].createInputQueue()
    nn_with_parser.inputs["texts"].setReusePreviousMessage(True)

    # filter and rename detection labels
    det_process_filter = pipeline.create(ImgDetectionsFilter).build(nn_with_parser.out)
    det_process_filter.setLabels(labels=[i for i in range(len(CLASS_NAMES))], keep=True)
    annotation_node = pipeline.create(AnnotationNode).build(
        det_process_filter.out,
        label_encoding={k: v for k, v in enumerate(CLASS_NAMES)},
    )

    # visualization
    visualizer.addTopic("Detections", annotation_node.out)
    visualizer.addTopic("Video", nn_with_parser.passthroughs["images"])

    def class_update_service(new_classes: list[str]):
        """Changes classes to detect based on the user input"""
        if len(new_classes) == 0:
            print("List of new classes empty, skipping.")
            return
        if len(new_classes) > MAX_NUM_CLASSES:
            print(
                f"Number of new classes ({len(new_classes)}) exceeds maximum number of classes ({MAX_NUM_CLASSES}), skipping."
            )
            return
        CLASS_NAMES = new_classes

        text_features = extract_text_embeddings(
            class_names=CLASS_NAMES, max_num_classes=MAX_NUM_CLASSES
        )
        inputNNData = dai.NNData()
        inputNNData.addTensor(
            "texts", text_features, dataType=dai.TensorInfo.DataType.U8F
        )
        textInputQueue.send(inputNNData)

        det_process_filter.setLabels(
            labels=[i for i in range(len(CLASS_NAMES))], keep=True
        )
        annotation_node.setLabelEncoding({k: v for k, v in enumerate(CLASS_NAMES)})
        print(f"Classes set to: {CLASS_NAMES}")

    def conf_threshold_update_service(new_conf_threshold: float):
        """Changes confidence threshold based on the user input"""
        CONFIDENCE_THRESHOLD = max(0, min(1, new_conf_threshold))
        nn_with_parser.getParser(0).setConfidenceThreshold(CONFIDENCE_THRESHOLD)
        print(f"Confidence threshold set to: {CONFIDENCE_THRESHOLD}:")

    def image_upload_service(image_data):
        image = base64_to_cv2_image(image_data["data"])
        image_features = extract_image_prompt_embeddings(image)
        print("Image features extracted, sending to model...")
        inputNNData = dai.NNData()
        inputNNData.addTensor(
            "texts", image_features, dataType=dai.TensorInfo.DataType.U8F
        )
        textInputQueue.send(inputNNData)

        filename = image_data["filename"]
        CLASS_NAMES = [filename.split(".")[0]]

        det_process_filter.setLabels(
            labels=[i for i in range(len(CLASS_NAMES))], keep=True
        )
        annotation_node.setLabelEncoding({k: v for k, v in enumerate(CLASS_NAMES)})
        print(f"Classes set to: {CLASS_NAMES}")

    visualizer.registerService("Class Update Service", class_update_service)
    visualizer.registerService(
        "Threshold Update Service", conf_threshold_update_service
    )
    visualizer.registerService("Image Upload Service", image_upload_service)

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
