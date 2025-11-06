from core.services.base_service import BaseService
from core.services.payloads.image_upload_payload import ImageUploadPayload
from core.services.service_name import ServiceName


class ImageUploadService(BaseService[ImageUploadPayload]):
    """Coordinates image upload flow: decode → extract → send → update labels."""

    NAME = ServiceName.IMAGE_UPLOAD

    def handle(self, payload: ImageUploadPayload) -> dict[str, any]:
        image_inputs, dummy = self._handler.process(payload)
        class_names = self._handler.get_class_names()

        self._controller.send_prompts_pair(
            image_inputs, dummy, class_names, self._handler.get_offset()
        )

        return {"ok": True, "class": class_names}
