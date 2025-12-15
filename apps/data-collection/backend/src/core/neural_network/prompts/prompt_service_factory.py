from core.neural_network.prompts.nn_prompts_controller import NnPromptsController
from core.neural_network.prompts.handlers_factory import HandlersFactory
from core.base_service import BaseService
from core.neural_network.prompts.front_end_prompt_services.class_update_service import (
    ClassUpdateService,
)
from core.neural_network.prompts.front_end_prompt_services.threshold_update_service import (
    ThresholdUpdateService,
)
from core.neural_network.prompts.front_end_prompt_services.image_upload_service import (
    ImageUploadService,
)
from core.neural_network.prompts.front_end_prompt_services.bbox_prompt_service import (
    BBoxPromptService,
)


class PromptServiceFactory:
    def __init__(
        self,
        controller: NnPromptsController,
        handlers: HandlersFactory,
    ):
        self.controller: NnPromptsController = controller
        self.handlers: HandlersFactory = handlers

    def build_services(self) -> list[BaseService]:
        return [
            ClassUpdateService(self.controller, self.handlers.class_update_handler),
            ThresholdUpdateService(self.controller),
            ImageUploadService(self.controller, self.handlers.image_update_handler),
            BBoxPromptService(self.controller, self.handlers.bbox_prompt_handler),
        ]
