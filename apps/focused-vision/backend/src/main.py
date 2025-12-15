import logging

import depthai as dai

import host_nodes
import pipeline_builders
from arguments import initialize_argparser
from depthai_nodes.node.extended_neural_network import ExtendedNeuralNetwork
from depthai_nodes.node.stage_2_neural_network import Stage2NeuralNetwork


logger = logging.getLogger(__name__)

_, args = initialize_argparser()

logger.error("Starting")
frame_type = dai.ImgFrame.Type.BGR888i
HIGH_RES_WIDTH, HIGH_RES_HEIGHT = 2000, 2000
LOW_RES_WIDTH, LOW_RES_HEIGHT = 640, 640
PEOPLE_DETECTION_MODEL = "luxonis/scrfd-person-detection:25g-640x640"
FACE_DETECTION_MODEL = "luxonis/yunet:320x240"
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
        input=rgb_low_res_out,
        input_resize_mode=dai.ImageManipConfig.ResizeMode.LETTERBOX,
        nn_source=FACE_DETECTION_MODEL,
        enable_detection_filtering=True,
    )
    largest_face_detection_naive = host_nodes.PickLargestBbox().build(
        face_detection_naive.out
    )
    face_detection_naive_as_img_det = (
        host_nodes.SafeImgDetectionsExtendedBridge().build(
            largest_face_detection_naive.out, ignore_angle=True
        )
    )
    switch_naive = host_nodes.Switch().build(
        face_detection_naive_as_img_det.out, rgb_low_res_out
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
        input=rgb_low_res_out,
        input_resize_mode=dai.ImageManipConfig.ResizeMode.LETTERBOX,
        nn_source=PEOPLE_DETECTION_MODEL,
        enable_detection_filtering=True,
    )
    largest_people_detection = host_nodes.PickLargestBbox().build(people_detection.out)
    largest_people_detection_as_img_detection = (
        host_nodes.SafeImgDetectionsExtendedBridge().build(
            largest_people_detection.out, ignore_angle=True
        )
    )
    largest_people_detection_cropped = host_nodes.CropPersonDetectionWaistDown(
        ymin_transformer=pipeline_builders.transform_ymin,
        ymax_transformer=pipeline_builders.transform_ymax,
    ).build(largest_people_detection_as_img_detection.out)
    face_people_gathered = pipeline.create(Stage2NeuralNetwork).build(
        img_frame=rgb_high_res_out,
        stage_1_nn=largest_people_detection_cropped.out,
        nn_source=FACE_DETECTION_MODEL,
        input_resize_mode=dai.ImageManipConfig.ResizeMode.LETTERBOX,
        fps=args.fps_limit,
        remap_detections=True,
    )
    face_detection_2_stage = host_nodes.FaceDetectionFromGatheredData().build(
        node_out=face_people_gathered.out
    )
    face_detection_2_stage_as_img_detection = (
        host_nodes.SafeImgDetectionsExtendedBridge().build(
            face_detection_2_stage.out, ignore_angle=True
        )
    )
    switch_2_stage = host_nodes.Switch().build(
        face_detection_2_stage_as_img_detection.out, rgb_high_res_out
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
    face_detection_with_tiling_nn = pipeline.create(ExtendedNeuralNetwork)
    face_detection_with_tiling_nn.build(
        input=rgb_high_res_out,
        input_resize_mode=dai.ImageManipConfig.ResizeMode.LETTERBOX,
        nn_source=FACE_DETECTION_MODEL,
        enable_detection_filtering=True,
        enable_tiling=True,
        input_size=(HIGH_RES_WIDTH, HIGH_RES_HEIGHT),
    )
    face_detection_with_tiling_nn.setConfidenceThreshold(0.75)
    face_detection_with_tiling_nn.setTilingGridSize((4, 4))
    largest_face_detection_tiling = host_nodes.PickLargestBbox().build(
        face_detection_with_tiling_nn.out
    )
    face_detection_tiling_as_img_det = (
        host_nodes.SafeImgDetectionsExtendedBridge().build(
            largest_face_detection_tiling.out, ignore_angle=True
        )
    )
    switch_tiling = host_nodes.Switch().build(
        face_detection_tiling_as_img_det.out, rgb_high_res_out
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
        pipeline.processTasks()
        key = visualizer.waitKey(1)
        counter += 1
        if counter % 100_000 == 0:
            logger.error("Running")
        if key == ord("q"):
            print("[MAIN] Got q key. Exiting...")
            break
