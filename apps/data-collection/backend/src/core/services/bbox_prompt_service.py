from core.services.base_service import BaseService
from core.services.payloads.bbox_prompt_payload import BBoxPromptPayload
from core.services.service_name import ServiceName


class BBoxPromptService(BaseService[BBoxPromptPayload]):
    NAME = ServiceName.BBOX_PROMPT

    def handle(self, payload: BBoxPromptPayload) -> dict[str, any]:
        image_inputs, dummy = self._handler.process(payload)
        class_names = self._handler.get_class_names()
        self._controller.send_prompts_pair(
            image_inputs, dummy, class_names, self._handler.get_offset()
        )

        return {"ok": True, "classes": class_names}
