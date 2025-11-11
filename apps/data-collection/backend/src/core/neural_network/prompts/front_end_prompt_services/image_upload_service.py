from pydantic import ValidationError
from core.base_service import BaseService
from core.neural_network.prompts.front_end_prompt_services.payloads.image_upload_payload import (
    ImageUploadPayload,
)
from core.service_name import ServiceName


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
