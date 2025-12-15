from core.base_service import BaseService
from core.dino_similarity.dino_selection_node import DinoSelectionNode
from pydantic import BaseModel, ValidationError


class ClickPayload(BaseModel):
    x: float
    y: float


class ClickPromptService(BaseService[ClickPayload]):
    NAME = "Click Prompt Service"

    def __init__(self, dino_process: DinoSelectionNode):
        self._dino_process = dino_process

    def handle(self, payload) -> dict:
        try:
            payload = ClickPayload.model_validate(payload)
        except ValidationError as e:
            self._dino_process._logger.info(f"WTF IS GOING ON {e}")
            return {"ok": False, "error": e.errors()}

        self._dino_process.set_selection_click(payload.x, payload.y)
        return {"ok": True}
