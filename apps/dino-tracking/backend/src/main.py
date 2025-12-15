import os
from pathlib import Path

os.environ.setdefault("DEPTHAI_LEVEL", "INFO")
from constants.yml_constants_loader import YamlFilesLoader
from core.annotations.annotations_control_services.annotation_mode_service import AnnotationModeService
from core.dino_similarity.prompting.FE_prompt_services.clear_selection_sevice import ClearSelectionService
from core.annotations.annotations_control_services.outlines_trigger_service import OutlinesTriggerService
from core.detections_tracking.threshold_service import ThresholdService

from dotenv import load_dotenv

from core.detections_tracking.heatmap_detection_node import HeatmapDetectionNode
from core.detections_tracking.tracker import Tracker

import depthai as dai

from depthai_nodes.node import ParsingNeuralNetwork

from core.annotations.outlines_overlay_node import OutlinesOverlayNode
from core.dino_similarity.prompting.FE_prompt_services.click_prompt_service import ClickPromptService
from core.dino_similarity.dino_selection_node import DinoSelectionNode
from core.annotations.dino_annotation_node import DinoAnnotationNode
from core.neural_network_builder import NNBuilder
from core.encoder import Encoder
from core.state_service import StateService


load_dotenv(override=True)


def main():
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

        dino_process = pipeline.create(DinoSelectionNode).build(
            frame_in=rgb_sensor,
            segmentations=seg_out,
            dino_embeddings=dino_out,
            sam_size=fastsam_nn.input_size,
            dino_size=dino_nn.input_size,
        )
        prompt_service = ClickPromptService(dino_process)
        clear_service = ClearSelectionService(dino_process)
        visualizer.registerService(prompt_service.NAME, prompt_service.handle)
        visualizer.registerService(clear_service.NAME, clear_service.handle)

        heatmap_det = pipeline.create(HeatmapDetectionNode).build(
            heatmap_in=dino_process.out
        )
        threshold_service = ThresholdService(heatmap_det)
        visualizer.registerService(threshold_service.NAME, threshold_service.handle)

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
        outlines_service = OutlinesTriggerService(outlines_node)
        visualizer.registerService(outlines_service.NAME, outlines_service.handle)

        annot_node = pipeline.create(DinoAnnotationNode).build(
            frame_msg=outlines_node.out,
            heatmap_in=dino_process.out,
            tracklets_in=tracker.out,
        )
        annotation_service = AnnotationModeService(annot_node)
        visualizer.registerService(annotation_service.NAME, annotation_service.handle)

        video_enc = Encoder(pipeline, constants.camera).encode(annot_node.out)

        visualizer.addTopic("Video", video_enc, "images")

        state_service = StateService(heatmap_det, annot_node, outlines_node)
        visualizer.registerService(state_service.NAME, state_service.handle)

        print("Pipeline created.")

        pipeline.start()
        visualizer.registerPipeline(pipeline)

        while pipeline.isRunning():
            key = visualizer.waitKey(1)
            if key == ord("q"):
                print("Received q. Exiting...")
                break


if __name__ == "__main__":
    main()
