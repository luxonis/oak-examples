from pydantic import BaseModel, ValidationError

from core.annotations.outlines_overlay_node import OutlinesOverlayNode
from core.base_service import BaseService


class OutlinesTogglePayload(BaseModel):
    active: bool


class OutlinesTriggerService(BaseService[OutlinesTogglePayload]):
    NAME = "Outlines Trigger Service"
    PAYLOAD_MODEL = OutlinesTogglePayload

    def __init__(self, outlines_node: OutlinesOverlayNode):
        self._outlines_node = outlines_node

    def on_validation_error(self, e: ValidationError) -> None:
        self._outlines_node._logger.info(
            f"Validation error in OutlinesTriggerService: {e}"
        )

    def handle_typed(self, payload: OutlinesTogglePayload) -> dict:
        self._outlines_node._logger.info(
            f"Setting outlines active state to {payload.active}"
        )
        self._outlines_node.set_active(payload.active)
        return {
            "ok": True,
            "outlines": self._outlines_node.get_active(),
        }
