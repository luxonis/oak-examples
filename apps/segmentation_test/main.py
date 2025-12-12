from dotenv import load_dotenv
import os

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
        size=(1280, 720),
        type=dai.ImgFrame.Type.BGR888i,
        fps=args.fps_limit,
    )

    model = dai.NNModelDescription("luxonis/fastsam-s:512x288")
    model.platform = platform
    archive = dai.NNArchive(dai.getModelFromZoo(model))
    w, h = archive.getInputSize()

    manip = pipeline.create(dai.node.ImageManip)
    manip.initialConfig.setOutputSize(w, h)
    manip.initialConfig.setFrameType(dai.ImgFrame.Type.BGR888i)
    manip.setMaxOutputFrameSize(w * h * 3)

    video_full.link(manip.inputImage)

    nn_node = pipeline.create(ParsingNeuralNetwork).build(
        manip.out,
        archive,
    )

    outlines_node = pipeline.create(DummyNode).build(
        video_full,
    )

    print("Pipeline created.")

    pipeline.start()

    while pipeline.isRunning():
        if 1 == ord("q"):
            print("Received q. Exiting...")
            break
