from pathlib import Path

import depthai as dai
from depthai_nodes.node import ParsingNeuralNetwork

from utils.arguments import initialize_argparser
from utils.visualizer_node import VisualizeLicensePlates

REQ_WIDTH, REQ_HEIGHT = (
    1920 * 2,
    1080 * 2,
)

_, args = initialize_argparser()

visualizer = dai.RemoteConnection(httpPort=8082)
device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()
platform = device.getPlatform().name
print(f"Platform: {platform}")

if platform != "RVC4":
    raise ValueError("This example is only supported for RVC4 platform.")

frame_type = dai.ImgFrame.Type.BGR888i

if args.fps_limit is None:
    args.fps_limit = 25
    print(
        f"\nFPS limit set to {args.fps_limit} for {platform} platform. If you want to set a custom FPS limit, use the --fps_limit flag.\n"
    )

with dai.Pipeline(device) as pipeline:
    print("Creating pipeline...")

    # vehicle detection model
    vehicle_det_model_description = dai.NNModelDescription.fromYamlFile(
        f"yolov6_nano_r2_coco.{platform}.yaml"
    )
    vehicle_det_model_nn_archive = dai.NNArchive(
        dai.getModelFromZoo(vehicle_det_model_description)
    )
    vehicle_det_model_w, vehicle_det_model_h = (
        vehicle_det_model_nn_archive.getInputSize()
    )

    # licence plate detection model
    lp_det_model_description = dai.NNModelDescription.fromYamlFile(
        f"license_plate_detection.{platform}.yaml"
    )
    lp_det_model_nn_archive = dai.NNArchive(
        dai.getModelFromZoo(lp_det_model_description)
    )
    lp_det_model_w, lp_det_model_h = lp_det_model_nn_archive.getInputSize()

    # ocr model
    ocr_model_description = dai.NNModelDescription.fromYamlFile(
        f"paddle_text_recognition.{platform}.yaml"
    )
    ocr_model_nn_archive = dai.NNArchive(dai.getModelFromZoo(ocr_model_description))
    ocr_model_w, ocr_model_h = ocr_model_nn_archive.getInputSize()

    # media/camera input
    if args.media_path:
        replay = pipeline.create(dai.node.ReplayVideo)
        replay.setReplayVideoFile(Path(args.media_path))
        replay.setOutFrameType(frame_type)
        replay.setLoop(True)
        replay_resize = pipeline.create(dai.node.ImageManip)
        replay_resize.initialConfig.setOutputSize(REQ_WIDTH, REQ_HEIGHT)
        replay_resize.initialConfig.setReusePreviousImage(False)
        replay_resize.setMaxOutputFrameSize(REQ_WIDTH * REQ_HEIGHT * 3)
        replay.out.link(replay_resize.inputImage)
    else:
        cam = pipeline.create(dai.node.Camera).build()
        cam_out = cam.requestOutput(
            (REQ_WIDTH, REQ_HEIGHT), frame_type, fps=args.fps_limit
        )
    input_node_out = replay_resize.out if args.media_path else cam_out

    # resize input to vehicle det model input size
    vehicle_det_resize_node = pipeline.create(dai.node.ImageManip)
    vehicle_det_resize_node.initialConfig.setOutputSize(
        vehicle_det_model_w, vehicle_det_model_h
    )
    vehicle_det_resize_node.initialConfig.setReusePreviousImage(False)
    input_node_out.link(vehicle_det_resize_node.inputImage)

    vehicle_det_nn: ParsingNeuralNetwork = pipeline.create(ParsingNeuralNetwork).build(
        vehicle_det_resize_node.out, vehicle_det_model_nn_archive
    )

    # process vehicle detections
    config_sender_node = pipeline.create(dai.node.Script)
    config_sender_node.setScriptPath(
        Path(__file__).parent / "utils/config_sender_script.py"
    )
    config_sender_node.setLogLevel(dai.LogLevel.CRITICAL)

    input_node_out.link(config_sender_node.inputs["frame_input"])
    vehicle_det_nn.out.link(config_sender_node.inputs["detections_input"])

    vehicle_crop_node = pipeline.create(dai.node.ImageManip)
    vehicle_crop_node.initialConfig.setReusePreviousImage(False)
    vehicle_crop_node.inputConfig.setReusePreviousMessage(False)
    vehicle_crop_node.inputImage.setReusePreviousMessage(False)
    vehicle_crop_node.setMaxOutputFrameSize(lp_det_model_w * lp_det_model_h * 3)

    config_sender_node.outputs["output_config"].link(vehicle_crop_node.inputConfig)
    config_sender_node.outputs["output_frame"].link(vehicle_crop_node.inputImage)

    # per vehicle license plate detection
    lp_config_sender = pipeline.create(dai.node.Script)
    lp_config_sender.setScriptPath(
        Path(__file__).parent / "utils/license_plate_sender_script.py"
    )
    lp_config_sender.setLogLevel(dai.LogLevel.CRITICAL)

    input_node_out.link(lp_config_sender.inputs["frame_input"])

    lp_det_nn = pipeline.create(ParsingNeuralNetwork).build(
        vehicle_crop_node.out, lp_det_model_nn_archive
    )
    config_sender_node.outputs["output_vehicle_detections"].link(
        lp_config_sender.inputs["detections_input"]
    )
    lp_det_nn.out.link(lp_config_sender.inputs["license_plate_detections"])

    # resize detected licence plates to ocr model input size
    lp_crop_node = pipeline.create(dai.node.ImageManip)
    vehicle_crop_node.initialConfig.setReusePreviousImage(False)
    lp_crop_node.inputConfig.setReusePreviousMessage(False)
    lp_crop_node.inputImage.setReusePreviousMessage(False)
    lp_crop_node.setMaxOutputFrameSize(ocr_model_w * ocr_model_h * 3)

    lp_config_sender.outputs["lp_crop_config"].link(lp_crop_node.inputConfig)
    lp_config_sender.outputs["lp_crop_frame"].link(lp_crop_node.inputImage)

    ocr_nn: ParsingNeuralNetwork = pipeline.create(ParsingNeuralNetwork).build(
        lp_crop_node.out, ocr_model_nn_archive
    )
    ocr_nn.getParser(0).setIgnoredIndexes(
        [
            0,
            11,
            12,
            13,
            14,
            15,
            16,
            17,
            44,
            45,
            46,
            47,
            48,
            49,
            76,
            77,
            78,
            79,
            80,
            81,
            82,
            83,
            84,
            85,
            86,
            87,
            88,
            89,
            90,
            91,
            93,
            94,
            95,
            96,
        ]
    )

    # annotation
    visualizer_node = pipeline.create(VisualizeLicensePlates)
    lp_config_sender.outputs["output_valid_detections"].link(
        visualizer_node.vehicle_detections
    )
    vehicle_det_nn.passthrough.link(visualizer_node.input_frame)
    ocr_nn.out.link(visualizer_node.ocr_results)
    lp_config_sender.outputs["output_valid_crops"].link(
        visualizer_node.lp_crop_detections
    )
    lp_crop_node.out.link(visualizer_node.lp_crop_images)

    # visualization
    visualizer.addTopic("License Plates", visualizer_node.out)

    print("Pipeline created.")

    pipeline.start()
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got q key. Exiting...")
            break
