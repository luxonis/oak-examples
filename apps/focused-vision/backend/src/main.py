import logging
import signal

import depthai as dai

import host_nodes
import pipeline_builders
from arguments import initialize_argparser
from depthai_nodes.node import (
    ImgDetectionsFilter,
    ExtendedNeuralNetwork,
    FrameCropper,
    GatherData,
    CoordinatesMapper,
    ParsingNeuralNetwork,
    Tiling,
)
import os
from pathlib import Path

logger = logging.getLogger(__name__)
shutdown_requested = False


def _handle_shutdown_signal(_signum, _frame):
    global shutdown_requested
    logger.info("Application received a stop signal. Stopping the app...")
    shutdown_requested = True


signal.signal(signal.SIGINT, _handle_shutdown_signal)
signal.signal(signal.SIGTERM, _handle_shutdown_signal)

_, args = initialize_argparser()

logger.error("Starting")
frame_type = dai.ImgFrame.Type.BGR888i
HIGH_RES_WIDTH, HIGH_RES_HEIGHT = 2000, 2000
LOW_RES_WIDTH, LOW_RES_HEIGHT = 640, 640
SCRIPT_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
DEPTHAI_MODELS_DIR = SCRIPT_DIR / "depthai_models"
PEOPLE_DETECTION_MODEL = dai.NNModelDescription.fromYamlFile(
    DEPTHAI_MODELS_DIR / "scrfd-person-detection.yaml"
)
FACE_DETECTION_MODEL = dai.NNModelDescription.fromYamlFile(
    DEPTHAI_MODELS_DIR / "yunet.yaml"
)
if not args.fps_limit:
    args.fps_limit = 13

visualizer = dai.RemoteConnection(httpPort=8082)
device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()
platform = device.getPlatform().name

if platform == "RVC2":
    logger.error(
        f"Detected platform is {platform}. Application can only run with RVC4. Exiting."
    )
    exit(1)

with dai.Pipeline(device) as pipeline:
    rgb_low_res_out, rgb_high_res_out = pipeline_builders.build_rgb(
        pipeline=pipeline,
        high_res=(HIGH_RES_WIDTH, HIGH_RES_HEIGHT),
        low_res=(LOW_RES_WIDTH, LOW_RES_HEIGHT),
        fps=args.fps_limit,
    )
    rgb_low_res_encoder = pipeline_builders.build_h264_stream(
        pipeline,
        src=rgb_low_res_out,
        size=(LOW_RES_WIDTH, LOW_RES_HEIGHT),
        fps=args.fps_limit,
        profile=dai.VideoEncoderProperties.Profile.H264_MAIN,
        assume_nv12=False,
    )
    # Naive face detection
    face_detection_naive = pipeline.create(ExtendedNeuralNetwork)
    face_detection_naive.build(
        inputImage=rgb_low_res_out,
        resizeMode=dai.ImageManipConfig.ResizeMode.LETTERBOX,
        nnSource=FACE_DETECTION_MODEL,
    )
    largest_face_detection_naive = pipeline.create(host_nodes.PickLargestBbox).build(
        face_detection_naive.out
    )
    switch_naive = pipeline.create(host_nodes.Switch).build(
        largest_face_detection_naive.out, rgb_low_res_out
    )
    face_cropper_naive = pipeline_builders.build_roi_cropper(
        pipeline=pipeline,
        preview_stream=switch_naive.rgb,
        det_stream=switch_naive.has_detections,
        out_size=(320, 320),
        frame_type=frame_type,
        padding=0.02,
        pool_size=5,
        cfg_queue_size=5,
    )
    black_image_generator_naive = host_nodes.BlackFrame().build(
        switch_naive.no_detections
    )
    face_crops_naive = host_nodes.Passthrough().build(
        face_cropper_naive, black_image_generator_naive.out
    )

    # 2-stage face detection
    people_detection = pipeline.create(ExtendedNeuralNetwork)
    people_detection.build(
        inputImage=rgb_low_res_out,
        resizeMode=dai.ImageManipConfig.ResizeMode.LETTERBOX,
        nnSource=PEOPLE_DETECTION_MODEL,
    )
    largest_people_detection = pipeline.create(host_nodes.PickLargestBbox).build(
        people_detection.out
    )
    largest_people_detection_cropped = host_nodes.CropPersonDetectionWaistDown(
        ymin_transformer=pipeline_builders.transform_ymin,
        ymax_transformer=pipeline_builders.transform_ymax,
    ).build(largest_people_detection.out)

    frame_cropper = pipeline.create(FrameCropper)
    face_det_nn = pipeline.create(ParsingNeuralNetwork).build(
        input=frame_cropper.out,
        nnSource=FACE_DETECTION_MODEL,
    )
    frame_cropper.fromImgDetections(
        inputImgDetections=largest_people_detection_cropped.out,
        outputSize=face_det_nn._nn_archive.getInputSize(),
        resizeMode=dai.ImageManipConfig.ResizeMode.LETTERBOX,
    ).build(
        inputImage=rgb_high_res_out,
    )
    face_det_collector = pipeline.create(GatherData).build(
        inputData=face_det_nn.out,
        inputReference=largest_people_detection_cropped.out,
        cameraFps=args.fps_limit,
    )
    face_det_coordinates_mapper = pipeline.create(CoordinatesMapper).build(
        toTransformationInput=rgb_high_res_out,
        fromTransformationInput=face_det_collector.out,
    )
    face_detection_2_stage = pipeline.create(
        host_nodes.FaceDetectionFromCollection
    ).build(node_out=face_det_coordinates_mapper.out)
    switch_2_stage = host_nodes.Switch().build(
        face_detection_2_stage.out, rgb_high_res_out
    )
    face_cropper_2_stage = pipeline_builders.build_roi_cropper(
        pipeline=pipeline,
        preview_stream=switch_2_stage.rgb,
        det_stream=switch_2_stage.has_detections,
        out_size=(320, 320),
        frame_type=frame_type,
        padding=0.02,
        pool_size=7,
        cfg_queue_size=5,
    )
    black_image_generator_2_stage = host_nodes.BlackFrame().build(
        switch_2_stage.no_detections
    )
    face_crops_2_stage = host_nodes.Passthrough().build(
        face_cropper_2_stage, black_image_generator_2_stage.out
    )

    # 1 stage with tiling
    nn_source = dai.NNArchive(dai.getModelFromZoo(FACE_DETECTION_MODEL))
    nn_input_size = nn_source.getInputSize()
    tiling = pipeline.create(Tiling).build(
        overlap=0.2,
        gridSize=(2, 2),
        canvasShape=(HIGH_RES_WIDTH, HIGH_RES_HEIGHT),
        resizeShape=nn_input_size,
        resizeMode=dai.ImageManipConfig.ResizeMode.LETTERBOX,
        globalDetection=True,
    )
    frame_cropper_tiling = (
        pipeline.create(FrameCropper)
        .fromManipConfigs(
            inputManipConfigs=tiling.out,
            maxOutputFrameSize=nn_input_size[0] * nn_input_size[1] * 3,
            waitForConfig=False,
        )
        .build(
            inputImage=rgb_high_res_out,
        )
    )
    face_detection_nn_tiling = pipeline.create(ParsingNeuralNetwork).build(
        input=frame_cropper_tiling.out,
        nnSource=nn_source,
    )
    face_detection_tiling_collector = pipeline.create(GatherData).build(
        inputData=face_detection_nn_tiling.out,
        inputReference=rgb_high_res_out,
        cameraFps=args.fps_limit,
        waitCountFn=lambda _: tiling.tileCount,
    )
    face_detection_tiling_remapper = pipeline.create(CoordinatesMapper).build(
        toTransformationInput=rgb_high_res_out,
        fromTransformationInput=face_detection_tiling_collector.out,
    )
    face_detections_tiling_merged = pipeline.create(
        host_nodes.MergeImgDetections
    ).build(collection_out=face_detection_tiling_remapper.out)
    face_detection_tiling_filter = (
        pipeline.create(ImgDetectionsFilter)
        .minConfidence(
            threshold=0.75,
        )
        .useNms(
            confThresh=0.75,
        )
        .build(
            input=face_detections_tiling_merged.out,
        )
    )
    largest_face_detection_tiling = host_nodes.PickLargestBbox().build(
        face_detection_tiling_filter.out
    )
    switch_tiling = host_nodes.Switch().build(
        largest_face_detection_tiling.out, rgb_high_res_out
    )
    head_cropper_tiling = pipeline_builders.build_roi_cropper(
        pipeline=pipeline,
        preview_stream=switch_tiling.rgb,
        det_stream=switch_tiling.has_detections,
        out_size=(320, 320),
        frame_type=frame_type,
        padding=0.02,
        pool_size=5,
        cfg_queue_size=5,
    )
    black_image_generator_tiling = host_nodes.BlackFrame().build(
        switch_tiling.no_detections
    )
    face_crops_tiling = host_nodes.Passthrough().build(
        head_cropper_tiling, black_image_generator_tiling.out
    )
    visualizer.addTopic("640x640 RGB", rgb_low_res_encoder, "low_res_image")
    visualizer.addTopic("NN detections", face_detection_naive.out, "low_res_image")
    # visualizer.addTopic("People detections", people_detection.out, "low_res_image")
    visualizer.addTopic(
        "Non-Focus Head Crops", face_crops_naive.out, "non_focus_head_crops"
    )
    visualizer.addTopic(
        "Focused Vision Head Crops", face_crops_2_stage.out, "focused_vision_head_crops"
    )
    visualizer.addTopic(
        "Focused with Tiling", face_crops_tiling.out, "focused_vision_tiling"
    )
    logger.error("Starting Pipeline")
    pipeline.start()
    visualizer.registerPipeline(pipeline)

    counter = 0
    while pipeline.isRunning():
        if shutdown_requested:
            pipeline.stop()
            break
        pipeline.processTasks()
        key = visualizer.waitKey(1)
        counter += 1
        if counter % 100_000 == 0:
            logger.error("Running")
        if key == ord("q"):
            print("[MAIN] Got q key. Exiting...")
            break
