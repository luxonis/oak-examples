from dotenv import load_dotenv
import os
import time

os.environ.setdefault("DEPTHAI_LEVEL", "INFO")
import depthai as dai
visualizer = dai.RemoteConnection(httpPort=8082)

from depthai_nodes.node import ParsingNeuralNetwork
from utils.arguments import initialize_argparser

from utils.dummy import DummyNode
from utils.outlines_overlay_node import OutlinesOverlayNode


load_dotenv(override=True)
_, args = initialize_argparser()


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
    w, h = archive.getInputSize()

    nn_node = pipeline.create(ParsingNeuralNetwork).build(
        video_full,
        archive,
    )

    # video_test = cam.requestOutput(
    #     size=(1280, 720),
    #     type=dai.ImgFrame.Type.BGR888i,
    #     fps=30,
    # )

    outlines = pipeline.create(OutlinesOverlayNode).build(
        video_full,
        nn_node.out,
    )

    dummy = pipeline.create(DummyNode).build(outlines.out)

    print("Pipeline created.")

    pipeline.start()

    while pipeline.isRunning():
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Received q. Exiting...")
            break
