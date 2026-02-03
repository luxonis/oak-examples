import logging as log

import depthai as dai

from config import parse_args, build_configuration
from app_config_service import GetCurrentParamsService
from camera import CameraSourceNode
from nn import NNDetectionNode
from prompting import FrameCacheNode, PromptingFEServices
from visualization import SegmentationOverlayNode

log.basicConfig(level=log.INFO)
logger = log.getLogger(__name__)


def main():
    device = dai.Device()
    visualizer = dai.RemoteConnection(serveFrontend=False)

    platform = device.getPlatformAsString()
    logger.info(f"Platform: {platform}")

    if platform != "RVC4":
        raise ValueError("This example is supported only on RVC4 platform")

    args = parse_args()
    config = build_configuration(platform, args)

    with dai.Pipeline(device) as pipeline:
        logger.info("Creating pipeline...")

        camera_source = pipeline.create(CameraSourceNode).build(cfg=config.video)
        logger.info("CameraSourceNode created")

        nn_node = pipeline.create(NNDetectionNode).build(
            input_frame=camera_source.bgr,
            cfg=config.nn,
        )
        logger.info("NNDetectionNode created")

        frame_cache_node = pipeline.create(FrameCacheNode).build(
            input_frame=camera_source.bgr,
        )
        logger.info("FrameCacheNode created")

        prompting_services = PromptingFEServices(
            update_classes=nn_node.update_classes,
            add_image_prompt=nn_node.add_image_prompt,
            add_bbox_prompt=nn_node.add_bbox_prompt,
            rename_image_prompt=nn_node.rename_image_prompt,
            delete_image_prompt=nn_node.delete_image_prompt,
            set_confidence_threshold=nn_node.set_confidence_threshold,
            get_last_frame=frame_cache_node.get_last_frame,
        )

        get_params_service = GetCurrentParamsService(
            get_nn_state=nn_node.get_state,
        )

        # Visualizer topics
        if config.nn.model.name == "yoloe":
            segmentation_viz_node = pipeline.create(SegmentationOverlayNode).build(
                input_detections=nn_node.detections,
                input_frame=camera_source.bgr,
                semantic=args.semantic_seg,
                cfg=config.video,
            )
            logger.info("SegmentationOverlayNode created")
            visualizer.addTopic("Video", segmentation_viz_node.encoded)
        else:
            visualizer.addTopic("Video", camera_source.encoded)
        visualizer.addTopic("Detections", nn_node.detections)

        # Register FE services
        visualizer.registerService(
            "Class Update Service", prompting_services.fe_class_update
        )
        visualizer.registerService(
            "Threshold Update Service", prompting_services.fe_threshold_update
        )
        visualizer.registerService(
            "Image Upload Service", prompting_services.fe_image_upload
        )
        visualizer.registerService(
            "BBox Prompt Service", prompting_services.fe_bbox_prompt
        )
        visualizer.registerService(
            "Rename Image Prompt Service", prompting_services.fe_rename_image_prompt
        )
        visualizer.registerService(
            "Delete Image Prompt Service", prompting_services.fe_delete_image_prompt
        )
        visualizer.registerService(
            "Get Current Params Service", get_params_service.handle
        )
        logger.info("FE services registered!")

        logger.info("Pipeline created. Starting...")
        pipeline.start()
        visualizer.registerPipeline(pipeline)
        logger.info("Pipeline running!")

        while pipeline.isRunning():
            key = visualizer.waitKey(1)
            pipeline.processTasks()
            if key == ord("q"):
                logger.info("Got 'q' key. Exiting...")
                break


if __name__ == "__main__":
    main()
