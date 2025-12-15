from pydantic import ValidationError
from core.base_service import BaseService
from core.neural_network.prompts.front_end_prompt_services.payloads.threshold_update_payload import (
    ThresholdUpdatePayload,
)
from core.service_name import ServiceName


class ThresholdUpdateService(BaseService[ThresholdUpdatePayload]):
    """Coordinates NN confidence threshold updates between handler, repository, and state."""

    NAME = ServiceName.THRESHOLD_UPDATE

    def handle(self, payload: ThresholdUpdatePayload) -> dict[str, any]:
        try:
            payload = ThresholdUpdatePayload.model_validate(payload)
        except ValidationError as e:
            return {"ok": False, "error": e.errors()}
        new_threshold = payload.threshold

        clamped = max(0.0, min(1.0, new_threshold))
        self._controller.set_confidence_threshold(clamped)

        return {"ok": True, "threshold": clamped}
