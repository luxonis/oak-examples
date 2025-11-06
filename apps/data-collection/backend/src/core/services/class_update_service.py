from core.services.base_service import BaseService
from core.services.payloads.class_update_payload import ClassUpdatePayload
from core.services.service_name import ServiceName


class ClassUpdateService(BaseService[ClassUpdatePayload]):
    """Coordinates text-based class updates across model, repository, and state."""

    NAME = ServiceName.CLASS_UPDATE

    def handle(self, payload: ClassUpdatePayload) -> dict[str, any]:
        text_inputs, dummy = self._handler.process(payload)
        new_classes = self._handler.get_class_names()
        self._controller.send_prompts_pair(
            dummy, text_inputs, new_classes, self._handler.get_offset()
        )

        return {"ok": True, "classes": new_classes}
