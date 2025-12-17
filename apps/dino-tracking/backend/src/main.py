import os

os.environ.setdefault("DEPTHAI_LEVEL", "INFO")

from core.dino_similarity.grid_extraction import DinoGridExtraction
from core.dino_similarity.reference_vector_node import ReferenceVectorNode
from core.dino_similarity.vector_manager import VectorManager
from pathlib import Path
from constants.yml_constants_loader import YamlFileLoader
from core.annotations.FE_annotations_control_services.annotation_mode_service import (
    AnnotationModeService,
)
from core.object_selection.FE_prompt_services.clear_selection_sevice import (
    ClearSelectionService,
)
from core.annotations.FE_annotations_control_services.outlines_trigger_service import (
    OutlinesTriggerService,
)
from core.detections_tracking.threshold_service import ThresholdService

from dotenv import load_dotenv

from core.detections_tracking.heatmap_to_bounding_box_node import (
    HeatmapToBoundingBoxNode,
)
from core.detections_tracking.tracker import Tracker

import depthai as dai

from depthai_nodes.node import ParsingNeuralNetwork

from core.annotations.outlines_overlay_node import OutlinesOverlayNode
from core.object_selection.FE_prompt_services.click_prompt_service import (
    ClickPromptService,
)
from core.annotations.dino_annotation_node import DinoAnnotationNode
from core.neural_network_builder import NNBuilder
from core.encoder import Encoder
from core.state_service import StateService
from core.dino_similarity.similarity_heatmap_node import SimilarityHeatmapNode
from core.object_selection.selection_mask_node import SelectionMaskNode

load_dotenv(override=True)


def main():
    constants = YamlFileLoader(Path(__file__).parent / "constants")
    camera_constants = constants.load("camera.yaml")
    nn_constants = constants.load("nn.yaml")

    visualizer = dai.RemoteConnection(httpPort=8082)

    device = dai.Device()
    platform = device.getPlatformAsString()
    print(f"Platform: {platform}")

    with dai.Pipeline(device) as pipeline:
        print("Creating pipeline...")

        camera = pipeline.create(dai.node.Camera).build()

        rgb_sensor = camera.requestOutput(
            size=camera_constants.resolution,
            type=dai.ImgFrame.Type.BGR888i,
            fps=camera_constants.fps,
        )

        fastsam_nn = NNBuilder(
            pipeline=pipeline,
            platform=platform,
            model_name=nn_constants.segmentation.model_name,
            nn_cls=ParsingNeuralNetwork,
        )
        seg_out = fastsam_nn.build(rgb_sensor)

        dino_nn = NNBuilder(
            pipeline=pipeline,
            platform=platform,
            model_name=nn_constants.dino.model_name,
            nn_cls=dai.node.NeuralNetwork,
        )
        dino_out = dino_nn.build(rgb_sensor)

        selection_node = pipeline.create(SelectionMaskNode).build(
            frame_in=rgb_sensor,
            segmentations=seg_out,
        )

        prompt_service = ClickPromptService(selection_node)
        clear_service = ClearSelectionService(selection_node)
        visualizer.registerService(prompt_service.NAME, prompt_service)
        visualizer.registerService(clear_service.NAME, clear_service)

        vector_manager = VectorManager(
            learn_thresh=0.85,
            learn_interval=30,
            learn_blend=0.3,
            combine_alpha=0.7,
        )

        dino_grid = pipeline.create(DinoGridExtraction).build(dino_in=dino_out)

        reference_node = pipeline.create(ReferenceVectorNode).build(
            manager=vector_manager,
            mask_in=selection_node.out,
            dino_in=dino_grid.out,
            dino_input_size=dino_nn.input_size,
        )

        similarity_node = pipeline.create(SimilarityHeatmapNode).build(
            manager=vector_manager,
            grid=reference_node.out,
            frame_in=rgb_sensor,
        )

        heatmap_det = pipeline.create(HeatmapToBoundingBoxNode).build(
            heatmap_in=similarity_node.out
        )
        threshold_service = ThresholdService(heatmap_det)
        visualizer.registerService(threshold_service.NAME, threshold_service)

        tracker = Tracker(
            pipeline=pipeline,
            detections=heatmap_det.out,
            frame=rgb_sensor,
        )

        tracker = tracker.build()

        outlines_node = pipeline.create(OutlinesOverlayNode).build(
            frame=rgb_sensor,
            segmentation=seg_out,
        )
        outlines_service = OutlinesTriggerService(outlines_node)
        visualizer.registerService(outlines_service.NAME, outlines_service)

        annot_node = pipeline.create(DinoAnnotationNode).build(
            frame_msg=outlines_node.out,
            heatmap_in=similarity_node.out,
            tracklets_in=tracker.out,
        )
        annotation_service = AnnotationModeService(annot_node)
        visualizer.registerService(annotation_service.NAME, annotation_service)

        video_enc = Encoder(pipeline, camera_constants).encode(annot_node.out)

        visualizer.addTopic("Video", video_enc, "images")

        state_service = StateService(heatmap_det, annot_node, outlines_node)
        visualizer.registerService(state_service.NAME, state_service)

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
