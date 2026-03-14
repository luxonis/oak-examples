from pathlib import Path
import logging

import depthai as dai
from depthai_nodes.node import ParsingNeuralNetwork, TilesPatcher

from fps_control import FPSController, PipelineHealthMonitor
from params_service import CurrentParamsService
from qr_scan import QRConfigService, QRDecoder
from tiling import DynamicTiling, TileGridOverlay, TilingConfigService

TILING_SIZE = (3840, 2160)
OUT_SIZE = (1920, 1080)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

visualizer = dai.RemoteConnection(httpPort=8082)
device = dai.Device()

with dai.Pipeline(device) as pipeline:
    logger.info("Creating pipeline...")

    platform = device.getPlatform()
    nn_archive = dai.NNArchive(
        dai.getModelFromZoo(
            dai.NNModelDescription.fromYamlFile(
                Path(f"qrdet_nano.{platform.name}.yaml")
            )
        )
    )

    camera = pipeline.create(dai.node.Camera).build()

    rgb_nn = camera.requestOutput(TILING_SIZE, type=dai.ImgFrame.Type.BGR888i)
    rgb_display = camera.requestOutput(OUT_SIZE, type=dai.ImgFrame.Type.BGR888i)

    fps_controller = pipeline.create(FPSController).build(
        nn_frames=rgb_nn, display_frames=rgb_display
    )

    dynamic_tiling = pipeline.create(DynamicTiling).build(
        img_output=fps_controller.rgb_nn,
        img_shape=TILING_SIZE,
        nn_shape=nn_archive.getInputSize(),
        resize_mode=dai.ImageManipConfig.ResizeMode.STRETCH,
    )

    nn = pipeline.create(ParsingNeuralNetwork).build(
        input=dynamic_tiling.out, nn_source=nn_archive
    )

    patcher = pipeline.create(TilesPatcher).build(
        img_frames=fps_controller.rgb_nn,
        nn=nn.out,
        conf_thresh=0.3,
        iou_thresh=0.2,
    )

    qr_decoder = pipeline.create(QRDecoder).build(
        input_frame=fps_controller.rgb_nn,
        input_detections=patcher.out,
    )

    grid_overlay = pipeline.create(TileGridOverlay).build(
        input_frame=fps_controller.rgb_display,
        get_tile_positions=dynamic_tiling.get_tile_positions,
        tile_size=TILING_SIZE,
    )

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

    pipeline_health_monitor = pipeline.create(PipelineHealthMonitor).build(
        pipeline=pipeline,
        initial_tile_count=dynamic_tiling.tile_count,
    )
    pipeline_health_monitor.out.link(fps_controller.target_fps)

    visualizer.addTopic("Video", encoder.out, "images")
    visualizer.addTopic("Visualizations", qr_decoder.out, "images")

    tiling_service = TilingConfigService(
        dynamic_tiling=dynamic_tiling,
        adjust_fps_from_tile_count=pipeline_health_monitor.adjust_fps_from_tile_count,
    )
    visualizer.registerService(tiling_service.NAME, tiling_service)

    qr_service = QRConfigService(qr_decoder=qr_decoder)
    visualizer.registerService(qr_service.NAME, qr_service)

    params_service = CurrentParamsService(
        dynamic_tiling=dynamic_tiling, qr_decoder=qr_decoder
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
