from pydantic import BaseModel, Field

from base_service import BaseService
from object_selection.mask_selection_node import MaskSelection


class ClickPayload(BaseModel):
    x: float = Field(..., ge=0.0, le=1.0)
    y: float = Field(..., ge=0.0, le=1.0)


class ObjectSelectionPrompt(BaseService[ClickPayload]):
    NAME = "Click Prompt Service"
    PAYLOAD_MODEL = ClickPayload

    def __init__(self, selection_node: MaskSelection):
        self._selection_node = selection_node

    def handle_typed(self, payload: ClickPayload) -> dict:
        self._selection_node.set_click(payload.x, payload.y)
        return {"ok": True}
