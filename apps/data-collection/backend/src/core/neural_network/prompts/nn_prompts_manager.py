from typing import List
import depthai as dai
from box import Box

from core.neural_network.prompts.nn_prompts_controller import NnPromptsController
from core.neural_network.prompts.frame_cache_node import FrameCacheNode
from core.neural_network.prompts.prompt_service_factory import (
    PromptServiceFactory,
)
from core.neural_network.prompts.prompt_encoders_manager import (
    PromptEncodersManager,
)
from core.neural_network.prompts.handlers_factory import HandlersFactory
from core.base_service import BaseService


class NNPromptsManager:
    """
    Facade for the neural-network subsystem.
    """

    def __init__(
        self,
        pipeline: dai.Pipeline,
        video_node: dai.Node.Output,
        config: Box,
        controller: NnPromptsController,
    ):
        self._pipeline: dai.Pipeline = pipeline
        self._video_node: dai.Node.Output = video_node
        self._config: Box = config
        self._controller: NnPromptsController = controller
        self._services: List[BaseService] = []

    def build(self):
        encoders = PromptEncodersManager(self._config)
        encoders.build()

        frame_cache = self._pipeline.create(FrameCacheNode).build(self._video_node)
        handlers = HandlersFactory(encoders, frame_cache)
        handlers.build()

        service_factory = PromptServiceFactory(self._controller, handlers)
        self._services = service_factory.build_services()

        text_prompt, image_prompt = encoders.prepare_initial_prompts()
        self._controller.send_prompts_pair(
            image_prompt,
            text_prompt,
            self._config.class_names,
            self._config.text_offset,
        )
        self._controller.set_confidence_threshold(self._config.detection_threshold)

    def register_services(self, visualizer: dai.RemoteConnection):
        for service in self._services:
            visualizer.registerService(service.name, service.handle)
