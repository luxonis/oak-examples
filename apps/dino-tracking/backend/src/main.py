from dotenv import load_dotenv
import os
os.environ.setdefault("DEPTHAI_LEVEL", "INFO")
import depthai as dai

from depthai_nodes.node import ParsingNeuralNetwork
from utils.arguments import initialize_argparser
from utils.input import create_input_node

from utils.outlines_overlay_node import OutlinesOverlayNode
from utils.segmentation_selection_service import SegmentationSelectionService
from utils.dino_seg_tracker_node import DinoSegTrackerNode
from utils.dino_annotation_node import DinoAnnotationNode
from utils.neural_network_builder import NNBuilder


load_dotenv(override=True)
_, args = initialize_argparser()

visualizer = dai.RemoteConnection(httpPort=8082)

device = dai.Device()
platform = device.getPlatformAsString()
print(f"Platform: {platform}")

with dai.Pipeline(device) as pipeline:
    print("Creating pipeline...")

    input_node = create_input_node(
        pipeline,
        platform,
        args.media_path,
    )

    video_full = input_node.requestOutput(
        size=(1280, 720),
        type=dai.ImgFrame.Type.BGR888i,
        fps=args.fps_limit,
    )

    fastsam_nn = NNBuilder(
        pipeline=pipeline,
        platform=platform,
        model_name="luxonis/fastsam-x:640x352",
        nn_cls=ParsingNeuralNetwork,
    )
    seg_out = fastsam_nn.build(video_full)

    dino_nn = NNBuilder(
        pipeline=pipeline,
        platform=platform,
        model_name="luxonis/dinov3-backbone:convnext-small-640x480",
        nn_cls=dai.node.NeuralNetwork,
    )
    dino_out = dino_nn.build(video_full)

    outlines_node = pipeline.create(OutlinesOverlayNode).build(
        video_full,
        seg_out,
    )

    tracker = pipeline.create(DinoSegTrackerNode).build(
        video_full,
        seg_out,
        dino_out,
        fs_size=fastsam_nn.input_size,
        dino_size=dino_nn.input_size,
    )

    annot_node = pipeline.create(DinoAnnotationNode).build(
        outlines_node.out,
        seg_out,
        tracker.out,
    )

    im = pipeline.create(dai.node.ImageManip)
    im.initialConfig.setOutputSize(1280, 720)
    im.initialConfig.setFrameType(dai.ImgFrame.Type.NV12)
    im.setMaxOutputFrameSize(int(1280 * 720 * 3))
    annot_node.out.link(im.inputImage)

    video_enc = pipeline.create(dai.node.VideoEncoder)

    video_enc.setDefaultProfilePreset(
        30,
        dai.VideoEncoderProperties.Profile.H264_MAIN,
    )

    im.out.link(video_enc.input)

    selection_service = SegmentationSelectionService(tracker)

    visualizer.addTopic("Video", video_enc.out, "images")
    visualizer.registerService(selection_service.NAME, selection_service.process)
    visualizer.registerService("Clear Selection Service", selection_service.clear)
    visualizer.registerService("Threshold Update Service", annot_node.set_confidence)
    visualizer.registerService("Annotation Mode Service", annot_node.set_mode)
    visualizer.registerService("Outlines Mode Service", outlines_node.set_mode)

    print("Pipeline created.")

    pipeline.start()
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Received q. Exiting...")
            break
