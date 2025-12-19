from pathlib import Path

import depthai as dai
from depthai_nodes.node import ParsingNeuralNetwork
from dotenv import load_dotenv

from annotations.detections_annotation_overlay_node import DetectionsAnnotationOverlay
from annotations.FE_annotations_control_services.annotation_mode_service import (
    AnnotationMode,
)
from annotations.FE_annotations_control_services.outlines_trigger_service import (
    OutlinesTrigger,
)
from annotations.outlines_overlay_node import OutlinesOverlay
from constants.yml_constants_loader import YamlFilesLoader
from detections_tracking.heatmap_to_detections_node import HeatmapToDetections
from detections_tracking.threshold_service import ThresholdUpdate
from detections_tracking.tracker import Tracker
from dino_similarity.dino_grid_extractor_node import DinoGridExtractor
from dino_similarity.reference_vectors.adaptive_reference_vector_node import (
    AdaptiveReferenceVector,
)
from dino_similarity.reference_vectors.reference_vector_from_selection_node import (
    ReferenceVectorFromSelection,
)
from dino_similarity.similarity_heatmap_node import SimilarityHeatmap
from encoder import Encoder
from FE_state_synchronization_service import FEStateSynchronization
from object_selection.FE_prompt_services.clear_selection_prompt_service import (
    ClearSelectionPrompt,
)
from object_selection.FE_prompt_services.object_selection_prompt_service import (
    ObjectSelectionPrompt,
)
from object_selection.mask_selection_node import MaskSelection

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

        segmentation_rgb = camera.requestOutput(
            size=constants.nn.segmentation.input_size,
            type=dai.ImgFrame.Type.BGR888i,
            fps=constants.camera.fps,
        )

        dino_rgb = camera.requestOutput(
            size=constants.nn.dino.input_size,
            type=dai.ImgFrame.Type.BGR888i,
            fps=constants.camera.fps,
        )

        segmentation_nn = pipeline.create(ParsingNeuralNetwork).build(
            input=segmentation_rgb, nn_source=constants.nn.segmentation.model_name
        )

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

        mask_selection = pipeline.create(MaskSelection).build(
            segmentations=segmentation_nn.out,
        )

        object_selection_prompt_service = ObjectSelectionPrompt(mask_selection)
        clear_selection_prompt_service = ClearSelectionPrompt(mask_selection)
        visualizer.registerService(
            object_selection_prompt_service.NAME, object_selection_prompt_service
        )
        visualizer.registerService(
            clear_selection_prompt_service.NAME, clear_selection_prompt_service
        )

        dino_grid = pipeline.create(DinoGridExtractor).build(dino_in=dino_nn.out)

        reference_vector = pipeline.create(ReferenceVectorFromSelection).build(
            mask_in=mask_selection.out,
            dino_in=dino_grid.out,
            dino_input_size=constants.nn.dino.input_size,
        )

        adaptive_reference_vector = pipeline.create(
            AdaptiveReferenceVector, constants.reference_adaptation
        )

        reference_vector.out.link(adaptive_reference_vector.init_input)

        similarity_heatmap = pipeline.create(SimilarityHeatmap).build(
            reference_vectors_in=adaptive_reference_vector.out,
            grid_in=dino_grid.out,
            frame_in=rgb_sensor,
        )
        similarity_heatmap.vector_out.link(adaptive_reference_vector.feedback_input)

        heatmap_to_detections = pipeline.create(HeatmapToDetections).build(
            heatmap_in=similarity_heatmap.out
        )
        threshold_service = ThresholdUpdate(heatmap_to_detections)
        visualizer.registerService(threshold_service.NAME, threshold_service)

        tracker = Tracker(
            pipeline=pipeline,
            detections=heatmap_to_detections.out,
            frame=rgb_sensor,
        )
        tracker = tracker.build()

        outlines_overlay = pipeline.create(OutlinesOverlay).build(
            frame=rgb_sensor,
            segmentation=segmentation_nn.out,
        )
        outlines_service = OutlinesTrigger(outlines_overlay)
        visualizer.registerService(outlines_service.NAME, outlines_service)

        detections_annotation_overlay = pipeline.create(
            DetectionsAnnotationOverlay
        ).build(
            frame_msg=outlines_overlay.out,
            heatmap_in=similarity_heatmap.out,
            tracklets_in=tracker.out,
        )
        annotation_service = AnnotationMode(detections_annotation_overlay)
        visualizer.registerService(annotation_service.NAME, annotation_service)

        video_encoded = Encoder(pipeline, constants.camera).encode(
            detections_annotation_overlay.out
        )

        visualizer.addTopic("Video", video_encoded, "images")

        state_synchronization_service = FEStateSynchronization(
            heatmap_to_detections, detections_annotation_overlay, outlines_overlay
        )
        visualizer.registerService(
            state_synchronization_service.NAME, state_synchronization_service
        )

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
