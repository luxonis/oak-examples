import os
from pathlib import Path

from constants.yml_constants_loader import YamlFilesLoader

os.environ.setdefault("DEPTHAI_LEVEL", "INFO")
from dotenv import load_dotenv

from core.detections_tracking.heatmap_detection_node import HeatmapDetectionNode
from core.detections_tracking.tracker import Tracker

import depthai as dai

from depthai_nodes.node import ParsingNeuralNetwork

from core.annotations.outlines_overlay_node import OutlinesOverlayNode
from core.dino_node.prompting.click_prompt_service import ClickPromptService
from core.dino_node.dino_process_node import DinoProcessNode
from core.annotations.dino_annotation_node import DinoAnnotationNode
from core.neural_network_builder import NNBuilder
from core.encoder import Encoder
from core.state_service import StateService


load_dotenv(override=True)

constants = YamlFilesLoader(Path(__file__).parent / "constants")
constants.load_all()

visualizer = dai.RemoteConnection(httpPort=8082)

device = dai.Device()
platform = device.getPlatformAsString()
print(f"Platform: {platform}")

with dai.Pipeline(device) as pipeline:
    print("Creating pipeline...")

    camera = pipeline.create(dai.node.Camera).build()

    rgb_sensor = camera.requestOutput(
        size=constants.camera.resolution,
        type=dai.ImgFrame.Type.BGR888i,
        fps=constants.camera.fps,
    )

    fastsam_nn = NNBuilder(
        pipeline=pipeline,
        platform=platform,
        model_name=constants.nn.segmentation.model_name,
        nn_cls=ParsingNeuralNetwork,
    )
    seg_out = fastsam_nn.build(rgb_sensor)

    dino_nn = NNBuilder(
        pipeline=pipeline,
        platform=platform,
        model_name=constants.nn.dino.model_name,
        nn_cls=dai.node.NeuralNetwork,
    )
    dino_out = dino_nn.build(rgb_sensor)

    dino_process = pipeline.create(DinoProcessNode).build(
        frame_in=rgb_sensor,
        segmentations=seg_out,
        dino_embeddings=dino_out,
        sam_size=fastsam_nn.input_size,
        dino_size=dino_nn.input_size,
    )

    heatmap_det = pipeline.create(HeatmapDetectionNode).build(
        heatmap_in=dino_process.out
    )

    tracker_factory = Tracker(
        pipeline=pipeline,
        detections=heatmap_det.out,
        frame=rgb_sensor,
    )

    tracker = tracker_factory.build()

    outlines_node = pipeline.create(OutlinesOverlayNode).build(
        frame=rgb_sensor,
        segmentation=seg_out,
    )

    annot_node = pipeline.create(DinoAnnotationNode).build(
        frame_msg=outlines_node.out,
        heatmap_in=dino_process.out,
        tracklets_in=tracker.out,
    )

    prompt_service = ClickPromptService(dino_process)
    state_service = StateService(heatmap_det, annot_node, outlines_node)

    video_enc = Encoder(pipeline, constants.camera).encode(annot_node.out)

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
