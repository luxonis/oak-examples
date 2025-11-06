from typing import List
import depthai as dai
from box import Box

from core.controllers.nn_prompts_controller import NnPromptsController
from core.infrastructure.frame_cache_node import FrameCacheNode
from core.infrastructure.neural_network.prompt_service_factory import (
    PromptServiceFactory,
)
from core.infrastructure.neural_network.prompt_encoders_manager import (
    PromptEncodersManager,
)
from core.infrastructure.neural_network.handlers_manager import HandlersManager
from core.services.base_service import BaseService


class NeuralNetworkManager:
    """
    Facade for the neural-network subsystem.
    """

    def __init__(
        self,
        pipeline: dai.Pipeline,
        input_node: dai.Node.Output,
        config: Box,
        controller: NnPromptsController,
    ):
        self._pipeline = pipeline
        self._input_node = input_node
        self._config = config
        self._controller = controller
        self._services: List[BaseService] = []

    def build(self):
        encoders = PromptEncodersManager(self._config)
        frame_cache = self._pipeline.create(FrameCacheNode).build(self._input_node)
        handlers = HandlersManager(encoders, frame_cache)
        service_manager = PromptServiceFactory(self._controller, handlers)
        self._services = service_manager.services
        self._controller.send_prompts_pair(
            encoders.image_prompt,
            encoders.text_prompt,
            self._config.class_names,
            self._config.text_offset,
        )

    def get_services(self) -> list[BaseService]:
        return self._services
