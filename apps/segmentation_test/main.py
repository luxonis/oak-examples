from dotenv import load_dotenv
import os
import time

os.environ.setdefault("DEPTHAI_LEVEL", "INFO")
import depthai as dai

from depthai_nodes.node import ParsingNeuralNetwork

from utils.fps_measure_node import FpsMeasureNode
from utils.outlines_overlay_node import OutlinesOverlayNode


load_dotenv(override=True)


device = dai.Device()
platform = device.getPlatformAsString()
print(f"Platform: {platform}")

with dai.Pipeline(device) as pipeline:
    print("Creating pipeline...")

    cam = pipeline.create(dai.node.Camera).build()

    video_full = cam.requestOutput(
        size=(512, 288),
        type=dai.ImgFrame.Type.BGR888i,
        fps=30,
    )

    model = dai.NNModelDescription("luxonis/fastsam-s:512x288")
    model.platform = platform
    archive = dai.NNArchive(dai.getModelFromZoo(model))

    nn_node = pipeline.create(ParsingNeuralNetwork).build(
        video_full,
        archive,
    )

    # ------------------------------------------------------------------
    # Single-input Host Node:
    #  - consumes only NN output
    #
    # When NN parsing slows down, overall FPS drops slightly
    # (e.g. ~30 → ~25), but the pipeline remains responsive
    # and does not freeze.
    # ------------------------------------------------------------------

    fps_node = pipeline.create(FpsMeasureNode).build(nn_node.out)

    # ------------------------------------------------------------------
    # Two-input Host Node (OutlinesOverlayNode):
    #  - video_test: 30 FPS camera stream
    #  - nn_node.out: ParsingNeuralNetwork output
    #
    # When many segments are detected, NN parsing becomes slower
    # (NN output FPS drops from ~30 to ~20 or lower).
    #
    # Because link_args(video, seg) is blocking, the Host Node runs
    # at the slower input rate. This throttles the video stream and
    # can cause FPS to drop significantly or to freeze completely.

    # PLEASE COMMENT OUT THE SINGLE-INPUT NODE ABOVE TO TEST THIS ONE.

    # ------------------------------------------------------------------

    # outlines = pipeline.create(OutlinesOverlayNode).build(
    #     video_full,
    #     nn_node.out,
    # )
    #
    # fps_node = pipeline.create(FpsMeasureNode).build(outlines.out)

    print("Pipeline created.")

    pipeline.start()

    while pipeline.isRunning():
        pipeline.processTasks()
        time.sleep(0.01)
        if 1 == ord("q"):
            print("Received q. Exiting...")
            break
