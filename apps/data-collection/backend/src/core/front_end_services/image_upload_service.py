from pydantic import ValidationError
from core.front_end_services.base_service import BaseService
from core.front_end_services.payloads.image_upload_payload import ImageUploadPayload
from core.front_end_services.service_name import ServiceName


class ImageUploadService(BaseService[ImageUploadPayload]):
    """Coordinates image upload flow: decode → extract → send → update labels."""

    NAME = ServiceName.IMAGE_UPLOAD

    def handle(self, payload: ImageUploadPayload) -> dict[str, any]:
        try:
            payload = ImageUploadPayload.model_validate(payload)
        except ValidationError as e:
            return {"ok": False, "error": e.errors()}
        image_inputs, dummy = self._handler.process(payload)
        class_names = self._handler.get_class_names()

        self._controller.send_prompts_pair(
            image_inputs, dummy, class_names, self._handler.get_offset()
        )

        return {"ok": True, "class": class_names}
