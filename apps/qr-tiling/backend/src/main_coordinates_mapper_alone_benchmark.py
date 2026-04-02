from pathlib import Path
import logging

import depthai as dai
from coordinates_mapper import CoordinatesMapper


TILING_SIZE = (1920 * 2, 1080 * 2)
OUT_SIZE = (1920, 1080)
DEFAULT_TILING_PARAMS = {
    "rows": 4,
    "cols": 4,
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
    FPS = 1000
    FPS_SLOW = 20
    benchmark_out_slow = pipeline.create(dai.node.BenchmarkOut)
    benchmark_out_slow.setFps(FPS_SLOW)
    bench_in_slow = benchmark_out_slow.input.createInputQueue()
    initialFrame = dai.ImgFrame()
    bench_in_slow.send(initialFrame)

    benchmark_out = pipeline.create(dai.node.BenchmarkOut)
    benchmark_out.setFps(FPS)
    bench_in = benchmark_out.input.createInputQueue()
    initialFrame = dai.ImgFrame()
    bench_in.send(initialFrame)
    detections_in_display_space = pipeline.create(CoordinatesMapper).build(
        fromTransformationInput=benchmark_out.out,
        toTransformationInput=benchmark_out_slow.out,
    )

    benchmark = pipeline.create(dai.node.BenchmarkIn)
    benchmark.sendReportEveryNMessages(1_000)
    detections_in_display_space.out.link(benchmark.input)
    bench_out = benchmark.report.createOutputQueue()

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
