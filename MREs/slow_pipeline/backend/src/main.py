import logging
import numpy as np

import depthai as dai
from coordinates_mapper import CoordinatesMapper
from frame_cropper import FrameCropper
from tiling import Tiling

TILING_SIZE = (1920 // 4, 1080 // 4)
OUT_SIZE = (1920 // 4, 1080 // 4)
RESIZE_SHAPE = (512, 288)
DEFAULT_TILING_PARAMS = {
    "rows": 4,
    "cols": 4,
    "overlap": 0.2,
    "global_detection": False,
    "grid_matrix": None,
}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

visualizer = dai.RemoteConnection(httpPort=8082)
device = dai.Device()

with dai.Pipeline(device) as pipeline:
    logger.info("Creating pipeline...")
    platform = device.getPlatform()
    FPS = 30
    rgb_nn_bench = pipeline.create(dai.node.BenchmarkOut)
    rgb_nn_bench.setFps(FPS)
    rgb_nn_in_q = rgb_nn_bench.input.createInputQueue()
    rgb_display_bench = pipeline.create(dai.node.BenchmarkOut)
    rgb_display_bench.setFps(FPS)
    rgb_display_in_q = rgb_display_bench.input.createInputQueue()
    initialFrame_nn = dai.ImgFrame()
    initialFrame_nn.setCvFrame(
        np.zeros((TILING_SIZE[1], TILING_SIZE[0], 3), dtype=np.uint8),
        type=dai.ImgFrame.Type.BGR888i,
    )
    initialFrame_display = dai.ImgFrame()
    initialFrame_display.setCvFrame(
        np.zeros((OUT_SIZE[1], OUT_SIZE[0], 3), dtype=np.uint8),
        type=dai.ImgFrame.Type.BGR888i,
    )
    rgb_nn_in_q.send(initialFrame_nn)
    rgb_display_in_q.send(initialFrame_display)
    rgb_display = rgb_display_bench.out
    rgb_nn = rgb_nn_bench.out

    tiling = pipeline.create(Tiling).build(
        trigger=rgb_display,
        overlap=DEFAULT_TILING_PARAMS["overlap"],
        gridSize=(DEFAULT_TILING_PARAMS["cols"], DEFAULT_TILING_PARAMS["rows"]),
        canvasShape=TILING_SIZE,
        resizeShape=RESIZE_SHAPE,
        resizeMode=dai.ImageManipConfig.ResizeMode.STRETCH,
        globalDetection=DEFAULT_TILING_PARAMS["global_detection"],
        gridMatrix=DEFAULT_TILING_PARAMS["grid_matrix"],
    )
    frame_cropper = (
        pipeline.create(FrameCropper)
        .fromManipConfigs(tiling.out)
        .build(
            inputImage=rgb_nn,
            outputSize=RESIZE_SHAPE,
            resizeMode=dai.ImageManipConfig.ResizeMode.STRETCH,
        )
    )
    # Comment out FROM HERE if you test the slow variant using the coordinates_mapper
    # benchmark = pipeline.create(dai.node.BenchmarkIn)
    # benchmark.sendReportEveryNMessages(1_000)
    # frame_cropper.out.link(benchmark.input)
    # bench_out = benchmark.report.createOutputQueue()
    # Comment out TO HERE if you test the slow variant using the coordinates_mapper

    # Comment out FROM HERE if you test without coordinates_mapper which is still fast
    coordinates_mapper = pipeline.create(CoordinatesMapper).build(
        toTransformationInput=rgb_nn,
        fromTransformationInput=frame_cropper.out,
    )

    benchmark = pipeline.create(dai.node.BenchmarkIn)
    benchmark.sendReportEveryNMessages(1_000)
    coordinates_mapper.out.link(benchmark.input)
    bench_out = benchmark.report.createOutputQueue()
    # Comment out TO HERE if you test without coordinates_mapper which is still fast

    logger.info("Pipeline created. Starting...")
    pipeline.start()
    visualizer.registerPipeline(pipeline)
    logger.info("Pipeline running!")

    while pipeline.isRunning():
        pipeline.processTasks()
        key = visualizer.waitKey(1)
        report = bench_out.tryGet()
        if report is not None:
            print(
                f"FPS: {report.fps}, expected: {DEFAULT_TILING_PARAMS['cols']*DEFAULT_TILING_PARAMS['rows']*FPS}"
            )
        if key == ord("q"):
            logger.info("Got 'q' key. Exiting...")
            break
