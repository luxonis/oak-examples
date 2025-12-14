import os
os.environ.setdefault("DEPTHAI_LEVEL", "INFO")
from dotenv import load_dotenv

from core.heatmap_detection_node import HeatmapDetectionNode
from core.tracker_factory import TrackerFactory

import depthai as dai

from depthai_nodes.node import ParsingNeuralNetwork
from utils.arguments import initialize_argparser

from core.annotations.outlines_overlay_node import OutlinesOverlayNode
from core.dino_node.prompting.click_prompt_service import ClickPromptService
from core.dino_node.dino_process_node import DinoProcessNode
from core.annotations.dino_annotation_node import DinoAnnotationNode
from core.neural_network_builder import NNBuilder
from core.video_provider import VideoProvider
from core.state_service import StateService


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

    dino_process = pipeline.create(DinoProcessNode).build(
        video_full,
        seg_out,
        dino_out,
        sam_size=fastsam_nn.input_size,
        dino_size=dino_nn.input_size,
    )

    heatmap_det = pipeline.create(HeatmapDetectionNode).build(
        dino_process.out
    )

    tracker_factory = TrackerFactory(
        pipeline=pipeline,
        detections_out=heatmap_det.out,
        video_out=video_full,
    )

    tracker = tracker_factory.build()

    annot_node = pipeline.create(DinoAnnotationNode).build(
        outlines_node.out,
        dino_process.out,
        tracker.out,
    )

    prompt_service = ClickPromptService(dino_process)

    video_enc = video.encode(annot_node.out)
    state_service = StateService(heatmap_det, annot_node, outlines_node)

    visualizer.addTopic("Video", video_enc, "images")
    visualizer.registerService(prompt_service.NAME_CLICK, prompt_service.handle)
    visualizer.registerService(prompt_service.NAME_CLEAR, prompt_service.clear)
    visualizer.registerService("Threshold Update Service", heatmap_det.set_confidence_threshold)
    visualizer.registerService("Annotation Mode Service", annot_node.set_mode)
    visualizer.registerService("Outlines Mode Service", outlines_node.set_active)
    visualizer.registerService(state_service.NAME, state_service.handle)

    print("Pipeline created.")

    pipeline.start()
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Received q. Exiting...")
            break
