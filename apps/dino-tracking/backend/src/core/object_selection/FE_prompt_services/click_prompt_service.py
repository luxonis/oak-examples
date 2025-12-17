from core.base_service import BaseService
from pydantic import BaseModel, ValidationError

from core.object_selection.selection_mask_node import SelectionMaskNode


class ClickPayload(BaseModel):
    x: float
    y: float


class ClickPromptService(BaseService[ClickPayload]):
    NAME = "Click Prompt Service"

    def __init__(self, selection_node: SelectionMaskNode):
        self._selection_node = selection_node

    def handle(self, payload) -> dict:
        try:
            payload = ClickPayload.model_validate(payload)
        except ValidationError as e:
            return {"ok": False, "error": e.errors()}

        self._selection_node.set_click(payload.x, payload.y)
        return {"ok": True}
