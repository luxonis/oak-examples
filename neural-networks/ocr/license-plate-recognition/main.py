from pathlib import Path
from datetime import timedelta

import depthai as dai
from depthai_nodes.node import FrameCropper, ParsingNeuralNetwork

from utils.arguments import initialize_argparser
from utils.visualizer_node import VisualizeLicensePlates
from utils.crop_regions import PlateRegions, VehicleRegions
from utils.gather_crops import GatherCrops

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

    vehicles = pipeline.create(VehicleRegions).build(vehicle_det_nn.out)
    vehicle_crop_node = (
        pipeline.create(FrameCropper)
        .fromImgDetections(
            inputImgDetections=vehicles.out,
            outputSize=(lp_det_model_w, lp_det_model_h),
            resizeMode=dai.ImageManipConfig.ResizeMode.STRETCH,
        )
        .build(inputImage=input_node_out)
    )

    lp_det_nn = pipeline.create(ParsingNeuralNetwork).build(
        vehicle_crop_node.out, lp_det_model_nn_archive
    )
    # Both crop inference stages must preserve result count and order for GatherData.
    lp_det_nn.input.setBlocking(True)
    lp_det_nn.setNumInferenceThreads(1)
    vehicle_plates = pipeline.create(GatherCrops).build(
        cameraFps=args.fps_limit,
        inputData=lp_det_nn.out,
        inputReference=vehicles.reference,
    )
    plates = pipeline.create(PlateRegions).build(
        vehicle_plates.out, (REQ_WIDTH, REQ_HEIGHT)
    )
    lp_crop_node = (
        pipeline.create(FrameCropper)
        .fromImgDetections(
            inputImgDetections=plates.out,
            outputSize=(ocr_model_w, ocr_model_h),
            resizeMode=dai.ImageManipConfig.ResizeMode.STRETCH,
        )
        .build(inputImage=input_node_out)
    )

    ocr_nn: ParsingNeuralNetwork = pipeline.create(ParsingNeuralNetwork).build(
        lp_crop_node.out, ocr_model_nn_archive
    )
    ocr_nn.input.setBlocking(True)
    ocr_nn.setNumInferenceThreads(1)
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

    # Keep the source detail in the display without sending 4K frames to the host.
    display_resize_node = pipeline.create(dai.node.ImageManip)
    display_resize_node.initialConfig.setOutputSize(1280, 720)
    display_resize_node.initialConfig.setReusePreviousImage(False)
    display_resize_node.setMaxOutputFrameSize(1280 * 720 * 3)
    input_node_out.link(display_resize_node.inputImage)

    # Pair each OCR output with its own crop before gathering by source frame.
    ocr_crops = pipeline.create(dai.node.Sync)
    # A zero Sync threshold does not match even identical timestamps.
    ocr_crops.setSyncThreshold(timedelta(microseconds=1))
    ocr_crops.setSyncAttempts(-1)
    ocr_crops.inputs["ocr"].setBlocking(True)
    ocr_crops.inputs["crop"].setBlocking(True)
    ocr_nn.out.link(ocr_crops.inputs["ocr"])
    ocr_nn.passthrough.link(ocr_crops.inputs["crop"])
    recognized_plates = pipeline.create(GatherCrops).build(
        cameraFps=args.fps_limit,
        inputData=ocr_crops.out,
        inputReference=plates.reference,
    )
    visualizer_node = pipeline.create(VisualizeLicensePlates).build(
        display_resize_node.out, recognized_plates.out
    )

    # visualization
    visualizer.addTopic("License Plates", visualizer_node.out)

    print("Pipeline created.")
    pipeline.start()
    print("Pipeline started.")
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got q key. Exiting...")
            break
