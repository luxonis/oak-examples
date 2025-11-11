from pydantic import ValidationError
from core.base_service import BaseService
from core.neural_network.prompts.front_end_prompt_services.payloads.bbox_prompt_payload import (
    BBoxPromptPayload,
)
from core.service_name import ServiceName


class BBoxPromptService(BaseService[BBoxPromptPayload]):
    NAME = ServiceName.BBOX_PROMPT

    def handle(self, payload: BBoxPromptPayload) -> dict[str, any]:
        try:
            payload = BBoxPromptPayload.model_validate(payload)
        except ValidationError as e:
            return {"ok": False, "error": e.errors()}

        image_inputs, dummy = self._handler.process(payload)
        class_names = self._handler.get_class_names()
        self._controller.send_prompts_pair(
            image_inputs, dummy, class_names, self._handler.get_offset()
        )

        return {"ok": True, "classes": class_names}
