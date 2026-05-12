from pathlib import Path
import logging

import depthai as dai
from depthai_nodes.node import (
    CoordinatesMapper,
    FrameCropper,
    ImgDetectionsFilter,
    MessageCollector,
    ParsingNeuralNetwork,
)
from tiling import Tiling, TileGridOverlay

from fps_control import FPSController, PipelineHealthMonitor
from params_service import CurrentParamsService
from qr_scan import QRConfigService, QRDecoder
from tiling import TilingConfigService
from tiling.merge_img_detections import MergeImgDetections

TILING_SIZE = (3840, 2160)
OUT_SIZE = (1920, 1080)
DEFAULT_TILING_PARAMS = {
    "rows": 2,
    "cols": 2,
    "overlap": 0.2,
    "global_detection": False,
    "grid_matrix": None,
}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
MODEL_DIR = Path(__file__).resolve().parent / "depthai_models"

visualizer = dai.RemoteConnection(httpPort=8082)
device = dai.Device()

with dai.Pipeline(device) as pipeline:
    logger.info("Creating pipeline...")

    platform = device.getPlatform()
    nn_archive = dai.NNArchive(
        dai.getModelFromZoo(
            dai.NNModelDescription.fromYamlFile(
                MODEL_DIR / f"qrdet_nano.{platform.name}.yaml"
            )
        )
    )
    camera = pipeline.create(dai.node.Camera).build()

    rgb_nn = camera.requestOutput(TILING_SIZE, type=dai.ImgFrame.Type.BGR888i)
    rgb_display = camera.requestOutput(OUT_SIZE, type=dai.ImgFrame.Type.NV12)

    fps_controller = pipeline.create(FPSController).build(
        nn_frames=rgb_nn, display_frames=rgb_display
    )

    tiling = pipeline.create(Tiling).build(
        overlap=DEFAULT_TILING_PARAMS["overlap"],
        gridSize=(DEFAULT_TILING_PARAMS["cols"], DEFAULT_TILING_PARAMS["rows"]),
        canvasShape=TILING_SIZE,
        resizeShape=nn_archive.getInputSize(),
        resizeMode=dai.ImageManipConfig.ResizeMode.STRETCH,
        globalDetection=DEFAULT_TILING_PARAMS["global_detection"],
        gridMatrix=DEFAULT_TILING_PARAMS["grid_matrix"],
    )
    print(f"tiling ID: {tiling.id=}")

    nn_input_size = nn_archive.getInputSize()
    tiling_cropper = (
        pipeline.create(FrameCropper)
        .fromManipConfigs(
            inputManipConfigs=tiling.out,
            maxOutputFrameSize=nn_input_size[0] * nn_input_size[1] * 3,
            waitForConfig=False,
        )
        .build(
            inputImage=fps_controller.rgb_nn,
        )
    )
    print(f"tiling_cropper ID: {tiling_cropper.id=}")

    nn = pipeline.create(ParsingNeuralNetwork).build(
        input=tiling_cropper.out, nnSource=nn_archive
    )

    collected_detections = pipeline.create(MessageCollector).build(
        inputData=nn.out,
        cameraFps=300000,
    )
    print(f"collected_detections ID: {collected_detections.id=}")

    detections_in_display_space = pipeline.create(CoordinatesMapper).build(
        toTransformationInput=fps_controller.rgb_nn,
        fromTransformationInput=collected_detections.out,
    )
    print(f"detections_in_display_space ID: {detections_in_display_space.id=}")

    merged_detections = pipeline.create(MergeImgDetections).build(
        input=detections_in_display_space.out
    )
    print(f"merged_detections ID: {merged_detections.id=}")

    filtered_detections = (
        pipeline.create(ImgDetectionsFilter)
        .useNms(
            confThresh=0.3,
            iouThresh=0.2,
        )
        .build(input=merged_detections.out)
    )
    print(f"filtered_detections ID: {filtered_detections.id=}")

    qr_decoder = pipeline.create(QRDecoder).build(
        input_frame=fps_controller.rgb_nn,
        input_detections=filtered_detections.out,
    )
    print(f"qr_decoder ID: {qr_decoder.id=}")

    pipeline_health_monitor = pipeline.create(PipelineHealthMonitor).build(
        pipeline=pipeline,
        initial_tile_count=tiling.tileCount,
    )
    print(f"pipeline_health_monitor ID: {pipeline_health_monitor.id=}")
    pipeline_health_monitor.out.link(fps_controller.target_fps)

    tiling_service = TilingConfigService(
        tiling=tiling,
        canvas_shape=TILING_SIZE,
        resize_shape=nn_archive.getInputSize(),
        resize_mode=dai.ImageManipConfig.ResizeMode.STRETCH,
        adjust_fps_from_tile_count=pipeline_health_monitor.adjust_fps_from_tile_count,
        initial_params=DEFAULT_TILING_PARAMS,
    )
    visualizer.registerService(tiling_service.NAME, tiling_service)

    grid_overlay = pipeline.create(TileGridOverlay).build(
        input_frame=fps_controller.rgb_display,
        get_tile_positions=tiling_service.get_tile_positions,
        tile_size=TILING_SIZE,
    )
    print(f"grid_overlay ID: {grid_overlay.id=}")

    grid_manip = pipeline.create(dai.node.ImageManip)
    grid_manip.initialConfig.setOutputSize(OUT_SIZE[0], OUT_SIZE[1])
    grid_manip.initialConfig.setFrameType(dai.ImgFrame.Type.NV12)
    grid_manip.setMaxOutputFrameSize(int(OUT_SIZE[0] * OUT_SIZE[1] * 3))
    grid_overlay.out.link(grid_manip.inputImage)

    encoder = pipeline.create(dai.node.VideoEncoder)
    encoder.setDefaultProfilePreset(
        fps=30,
        profile=dai.VideoEncoderProperties.Profile.H264_MAIN,
    )
    grid_manip.out.link(encoder.input)

    visualizer.addTopic("Video", encoder.out, "images")
    visualizer.addTopic("Visualizations", qr_decoder.out, "images")

    qr_service = QRConfigService(qr_decoder=qr_decoder)
    visualizer.registerService(qr_service.NAME, qr_service)

    params_service = CurrentParamsService(
        current_tiling_params=lambda: tiling_service.current_params,
        qr_decoder=qr_decoder,
    )
    visualizer.registerService(params_service.NAME, params_service)

    logger.info("Pipeline created. Starting...")
    pipeline.start()
    visualizer.registerPipeline(pipeline)
    logger.info("Pipeline running!")

    while pipeline.isRunning():
        pipeline.processTasks()
        key = visualizer.waitKey(1)
        if key == ord("q"):
            logger.info("Got 'q' key. Exiting...")
            break
