import depthai as dai
from config.system_configuration import SystemConfiguration
from core.front_end_services.export_service import ExportService
from core.neural_network.prompts.nn_prompts_manager import NNPromptsManager
from core.neural_network.pipeline.nn_pipeline_setup import NNPipelineBuilder
from core.snapping.snaps_manager import SnappingServiceManager
from core.video.video_factory import VideoFactory


def main():
    device = dai.Device()
    visualizer = dai.RemoteConnection(serveFrontend=False)

    platform = device.getPlatformAsString()

    if platform != "RVC4":
        raise ValueError("This example is supported only on RVC4 platform")

    config = SystemConfiguration(platform)
    config.build()

    with dai.Pipeline(device) as pipeline:
        print("Creating pipeline...")

        video_factory = VideoFactory(pipeline, config.get_video_config())
        visualizer.addTopic("Video", video_factory.get_encoded_output())
        video_node = video_factory.get_video_node()

        nn_pipeline = NNPipelineBuilder(
            pipeline,
            video_node,
            config.get_neural_network_config(),
        )
        nn_pipeline.build()
        visualizer.addTopic("Annotations", nn_pipeline.annotation_node.out)

        prompts_manager = NNPromptsManager(
            pipeline, video_node, config.get_prompts_config(), nn_pipeline.controller
        )
        prompts_manager.build()
        prompts_manager.register_services(visualizer)

        snaps_manager = SnappingServiceManager(
            pipeline,
            video_node,
            nn_pipeline.tracker,
            nn_pipeline.detections_bridge,
            config.get_snaps_config(),
        )
        snaps_manager.build()
        snaps_manager.register_service(visualizer)

        export_service = ExportService(
            nn_pipeline.controller.get_model_state(), snaps_manager.get_engine()
        )
        visualizer.registerService(export_service.name, export_service.handle)

        print("Pipeline created.")
        pipeline.start()
        visualizer.registerPipeline(pipeline)

        while pipeline.isRunning():
            pipeline.processTasks()
            visualizer.waitKey(1)


if __name__ == "__main__":
    main()
