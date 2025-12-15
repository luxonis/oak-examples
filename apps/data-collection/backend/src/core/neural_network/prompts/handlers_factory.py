from core.neural_network.prompts.handlers.base_prompt_handler import BasePromptHandler
from core.neural_network.prompts.handlers.text_prompt_handler import TextPromptHandler
from core.neural_network.prompts.handlers.image_prompt_handler import ImagePromptHandler
from core.neural_network.prompts.handlers.bbox_prompt_handler import BBoxPromptHandler
from core.neural_network.prompts.frame_cache_node import FrameCacheNode
from core.neural_network.prompts.prompt_encoders_manager import (
    PromptEncodersManager,
)


class HandlersFactory:
    def __init__(self, encoders: PromptEncodersManager, frame_cache: FrameCacheNode):
        self._encoders = encoders
        self._frame_cache = frame_cache
        self.class_update_handler: BasePromptHandler = None
        self.image_update_handler: BasePromptHandler = None
        self.bbox_prompt_handler: BasePromptHandler = None

    def build(self):
        self.class_update_handler = self._class_update_handler()
        self.image_update_handler = self._image_update_handler()
        self.bbox_prompt_handler = self._bbox_prompt_handler()

    def _class_update_handler(self) -> TextPromptHandler:
        return TextPromptHandler(self._encoders.textual_encoder)

    def _image_update_handler(self) -> ImagePromptHandler:
        return ImagePromptHandler(self._encoders.visual_encoder)

    def _bbox_prompt_handler(self) -> BBoxPromptHandler:
        return BBoxPromptHandler(self._encoders.visual_encoder, self._frame_cache)
