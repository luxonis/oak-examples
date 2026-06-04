import logging as log
import signal

import depthai as dai

from config import parse_args, build_configuration
from app_config_service import GetAppConfigService
from camera import CameraSourceNode
from nn import NNDetectionNode
from tracking import build_tracker_node
from prompting import FrameCacheNode, PromptingFEServices
from snapping import SnappingNode

log.basicConfig(level=log.INFO)
logger = log.getLogger(__name__)
shutdown_requested = False


def _handle_shutdown_signal(_signum, _frame):
    global shutdown_requested
    logger.info("Application received a stop signal. Stopping the app...")
    shutdown_requested = True


signal.signal(signal.SIGINT, _handle_shutdown_signal)
signal.signal(signal.SIGTERM, _handle_shutdown_signal)


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

        tracker_node = build_tracker_node(
            pipeline=pipeline,
            input_frame=camera_source.bgr,
            input_detections=nn_node.detections,
            cfg=config.tracker,
        )
        logger.info("TrackerNode created")

        snapping_node = pipeline.create(SnappingNode).build(
            input_frame=camera_source.bgr,
            input_detections=nn_node.detections,
            input_tracklets=tracker_node.out,
            cfg=config.snaps,
        )
        logger.info("SnappingNode created!")

        frame_cache_node = pipeline.create(FrameCacheNode).build(
            input_frame=camera_source.bgr,
        )
        logger.info("FrameCacheNode created")

        prompting_services = PromptingFEServices(
            update_classes=nn_node.update_classes,
            update_visual_prompt=nn_node.update_visual_prompt,
            set_confidence_threshold=nn_node.set_confidence_threshold,
            get_last_frame=frame_cache_node.get_last_frame,
        )

        get_config_service = GetAppConfigService(
            get_nn_state=nn_node.get_state,
            get_snap_conditions_config=snapping_node.get_snap_conditions_config,
        )

        # Visualizer topics
        visualizer.addTopic("Video", camera_source.encoded)
        visualizer.addTopic("Annotations", nn_node.detections_extended)

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
            "Snap Collection Service", snapping_node.fe_update_conditions
        )
        visualizer.registerService("Get App Config Service", get_config_service.handle)
        logger.info("FE services registered!")

        logger.info("Pipeline created. Starting...")
        pipeline.start()
        visualizer.registerPipeline(pipeline)
        logger.info("Pipeline running!")

        while pipeline.isRunning():
            if shutdown_requested:
                pipeline.stop()
                break
            key = visualizer.waitKey(1)
            pipeline.processTasks()
            if key == ord("q"):
                logger.info("Got 'q' key. Exiting...")
                break


if __name__ == "__main__":
    main()
