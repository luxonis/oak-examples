from core.base_service import BaseService
from core.annotations.outlines_overlay_node import OutlinesOverlayNode
from pydantic import BaseModel, ValidationError


class OutlinesTogglePayload(BaseModel):
    active: bool


class OutlinesTriggerService(BaseService[OutlinesTogglePayload]):
    NAME = "Outlines Trigger Service"

    def __init__(self, outlines_node: OutlinesOverlayNode):
        self._outlines_node = outlines_node

    def handle(self, payload) -> dict:
        try:
            payload = OutlinesTogglePayload.model_validate(payload)
        except ValidationError as e:
            self._outlines_node._logger.info(f"Validation error in OutlinesTriggerService:{e}")
            return {"ok": False, "error": e.errors()}
        self._outlines_node._logger.info(f"Setting outlines active state to {payload.active}")
        self._outlines_node.set_active(payload.active)
        return {
            "ok": True,
            "outlines": self._outlines_node.get_active(),
        }
