from core.controllers.nn_prompts_controller import NnPromptsController
from core.infrastructure.neural_network.handlers_manager import HandlersManager
from core.services.base_service import BaseService
from core.services.class_update_service import ClassUpdateService
from core.services.threshold_update_service import ThresholdUpdateService
from core.services.image_upload_service import ImageUploadService
from core.services.bbox_prompt_service import BBoxPromptService


class PromptServiceFactory:
    def __init__(
        self,
        controller: NnPromptsController,
        handlers: HandlersManager,
    ):
        self.controller = controller
        self.handlers = handlers
        self.services = self._build_services()

    def _build_services(self) -> list[BaseService]:
        return [
            ClassUpdateService(self.controller, self.handlers.class_update_handler),
            ThresholdUpdateService(self.controller),
            ImageUploadService(self.controller, self.handlers.image_update_handler),
            BBoxPromptService(self.controller, self.handlers.bbox_prompt_handler),
        ]
