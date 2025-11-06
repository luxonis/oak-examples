import depthai as dai

from config.system_configuration import SystemConfiguration
from core.model_state import ModelState
from core.infrastructure.neural_network.neural_network_manager import (
    NeuralNetworkManager,
)
from core.infrastructure.neural_network.nn_pipeline_setup import NNPipelineSetup
from core.infrastructure.snaps.snaps_manager import SnapsManager
from core.infrastructure.video_factory import VideoFactory
from core.infrastructure.export.export_manager import ExportManager


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
        model_state = ModelState()

        video_factory = VideoFactory(pipeline, config.get_video_config())
        visualizer.addTopic("Video", video_factory.get_encoded_output())
        input_node = video_factory.get_input_node()

        nn_pipeline = NNPipelineSetup(
            pipeline, input_node, config.get_neural_network_config(), model_state
        )
        nn_pipeline.build()
        visualizer.addTopic("Annotations", nn_pipeline.annotation_node.out)

        nn_manager = NeuralNetworkManager(
            pipeline, input_node, config.get_prompts_config(), nn_pipeline.controller
        )
        nn_manager.build()
        for service in nn_manager.get_services():
            visualizer.registerService(service.name, service.handle)

        snaps_manager = SnapsManager(
            pipeline,
            input_node,
            nn_pipeline.tracker,
            nn_pipeline.detections,
            config.get_snaps_config(),
        )
        snaps_service = snaps_manager.get_service()
        visualizer.registerService(snaps_service.name, snaps_service.handle)

        export_manager = ExportManager(model_state, snaps_manager.get_engine())
        export_service = export_manager.get_service()
        visualizer.registerService(export_service.name, export_service.handle)

        print("Pipeline created.")
        pipeline.start()
        visualizer.registerPipeline(pipeline)

        while pipeline.isRunning():
            pipeline.processTasks()
            visualizer.waitKey(1)


if __name__ == "__main__":
    main()
