from dotenv import load_dotenv
import os
import time

os.environ.setdefault("DEPTHAI_LEVEL", "INFO")
import depthai as dai

from depthai_nodes.node import ParsingNeuralNetwork
from utils.arguments import initialize_argparser

from utils.dummy import DummyNode


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
        fps=40,
    )

    model = dai.NNModelDescription("luxonis/fastsam-s:512x288")
    model.platform = platform
    archive = dai.NNArchive(dai.getModelFromZoo(model))
    w, h = archive.getInputSize()

    nn_node = pipeline.create(ParsingNeuralNetwork).build(
        video_full,
        archive,
    )

    outlines_node = pipeline.create(DummyNode).build(nn_node.out)

    print("Pipeline created.")

    pipeline.start()

    while pipeline.isRunning():
        pipeline.processTasks()
        time.sleep(0.01)
        if 1 == ord("q"):
            print("Received q. Exiting...")
            break
