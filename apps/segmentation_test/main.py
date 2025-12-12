from dotenv import load_dotenv
import os

os.environ.setdefault("DEPTHAI_LEVEL", "INFO")
import depthai as dai

from depthai_nodes.node import ParsingNeuralNetwork
from utils.arguments import initialize_argparser

from utils.outlines_overlay_node import DummyNode
from utils.neural_network_builder import NNBuilder
from utils.video_provider import VideoProvider


load_dotenv(override=True)
_, args = initialize_argparser()

visualizer = dai.RemoteConnection(httpPort=8082)

device = dai.Device()
platform = device.getPlatformAsString()
print(f"Platform: {platform}")

with dai.Pipeline(device) as pipeline:
    print("Creating pipeline...")

    video = VideoProvider(
        pipeline=pipeline,
        platform=platform,
        fps_limit=args.fps_limit,
        media_path=args.media_path,
    )

    video_full = video.get_main_stream()

    fastsam_nn = NNBuilder(
        pipeline=pipeline,
        platform=platform,
        model_name="luxonis/fastsam-s:512x288",
        nn_cls=ParsingNeuralNetwork,
    )
    seg_out = fastsam_nn.build(video_full)

    outlines_node = pipeline.create(DummyNode).build(
        video_full,
        seg_out,
    )

    video_enc = video.encode(outlines_node.out)

    visualizer.addTopic("Video", video_enc, "images")

    print("Pipeline created.")

    pipeline.start()
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Received q. Exiting...")
            break
