import depthai as dai

from core.services.base_service import BaseService


class SystemContext:
    """Holds runtime-specific resources (hardware and visualization)."""

    def __init__(self, platform: str | None = None):
        self.device = dai.Device()
        self.visualizer = dai.RemoteConnection(serveFrontend=False)
        self.platform = platform or self.device.getPlatformAsString()

    def register_service(self, service: BaseService) -> None:
        """Registers a service in the system context."""
        self.visualizer.registerService(service.name(), service.handle)

    def register_services(self, services: list[BaseService]) -> None:
        """Registers multiple services in the system context."""
        for service in services:
            self.register_service(service)

    def add_visualizer_topic(self, topic: dai.Node.Output, name: str = "Video") -> None:
        """Adds an annotations topic to the visualizer."""
        self.visualizer.addTopic(name, topic)

    def register_pipeline(self, pipeline: dai.Pipeline) -> None:
        """Registers a pipeline with the visualizer."""
        self.visualizer.registerPipeline(pipeline)
