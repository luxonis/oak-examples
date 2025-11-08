from pydantic import ValidationError
from core.front_end_services.base_service import BaseService
from core.front_end_services.payloads.bbox_prompt_payload import BBoxPromptPayload
from core.front_end_services.service_name import ServiceName


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
