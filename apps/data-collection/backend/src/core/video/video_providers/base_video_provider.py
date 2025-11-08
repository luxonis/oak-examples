from abc import ABC, abstractmethod
import depthai as dai
from config.config_data_classes import VideoConfig


class BaseVideoProvider(ABC):
    """Abstract interface for any DepthAI video input source."""

    def __init__(self, pipeline: dai.Pipeline, config: VideoConfig):
        self._pipeline = pipeline
        self._config = config

    @abstractmethod
    def get_video_node(self) -> dai.Node.Output:
        """Return BGR888i output for NN input."""
        pass

    @abstractmethod
    def get_nv12_output(self) -> dai.Node.Output:
        """Return NV12 output for visualization."""
        pass
