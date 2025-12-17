from core.dino_similarity.reference_vectors.adaptive_reference_vector_node import (
    AdaptiveReferenceVectorNode,
)
from core.dino_similarity.grid_extraction import DinoGridExtracorNode
from core.dino_similarity.reference_vectors.selection_reference_extractor_node import (
    SelectionReferenceExtractorNode,
)
from pathlib import Path
from constants.yml_constants_loader import YamlFilesLoader
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

from core.detections_tracking.heatmap_to_detections_node import (
    HeatmapToDetectionsNode,
)
from core.detections_tracking.tracker import Tracker

import depthai as dai

from depthai_nodes.node import ParsingNeuralNetwork

from core.annotations.outlines_overlay_node import OutlinesOverlayNode
from core.object_selection.FE_prompt_services.click_prompt_service import (
    ClickPromptService,
)
from core.annotations.dino_annotation_node import DinoAnnotationNode
from core.encoder import Encoder
from core.state_service import StateService
from core.dino_similarity.similarity_heatmap_node import SimilarityHeatmapNode
from core.object_selection.selection_mask_node import SelectionMaskNode

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

        fastsam_rgb = camera.requestOutput(
            size=constants.nn.segmentation.input_size,
            type=dai.ImgFrame.Type.BGR888i,
            fps=constants.camera.fps,
        )

        dino_rgb = camera.requestOutput(
            size=constants.nn.dino.input_size,
            type=dai.ImgFrame.Type.BGR888i,
            fps=constants.camera.fps,
        )

        fastsam_nn = pipeline.create(ParsingNeuralNetwork).build(
            input=fastsam_rgb, nn_source=constants.nn.segmentation.model_name
        )
        segmentation_out = fastsam_nn.out

        dino_nn = pipeline.create(dai.node.NeuralNetwork).build(
            input=dino_rgb,
            nnArchive=dai.NNArchive(
                dai.getModelFromZoo(
                    dai.NNModelDescription(
                        model=constants.nn.dino.model_name, platform=platform
                    )
                )
            ),
        )
        dino_out = dino_nn.out

        selection_node = pipeline.create(SelectionMaskNode).build(
            frame_in=rgb_sensor,
            segmentations=segmentation_out,
        )

        prompt_service = ClickPromptService(selection_node)
        clear_service = ClearSelectionService(selection_node)
        visualizer.registerService(prompt_service.NAME, prompt_service)
        visualizer.registerService(clear_service.NAME, clear_service)

        dino_grid = pipeline.create(DinoGridExtracorNode).build(dino_in=dino_out)

        reference_node = pipeline.create(SelectionReferenceExtractorNode).build(
            mask_in=selection_node.out,
            dino_in=dino_grid.out,
            dino_input_size=constants.nn.dino.input_size,
        )

        vector_manager = pipeline.create(
            AdaptiveReferenceVectorNode, constants.reference_adaptation
        )

        reference_node.out.link(vector_manager.init_input)

        similarity_node = pipeline.create(SimilarityHeatmapNode).build(
            references_in=vector_manager.out,
            grid_in=dino_grid.out,
            frame_in=rgb_sensor,
        )
        similarity_node.vector_out.link(vector_manager.feedback_input)

        heatmap_det = pipeline.create(HeatmapToDetectionsNode).build(
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
            segmentation=segmentation_out,
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

        video_enc = Encoder(pipeline, constants.camera).encode(annot_node.out)

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
