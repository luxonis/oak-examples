from core.base_service import BaseService
from core.dino_node.dino_process_node import DinoProcessNode
from pydantic import BaseModel


class ClickPayload(BaseModel):
    x: int
    y: int


class ClickPromptService(BaseService[ClickPayload]):
    NAME = "Click Prompt Service"
    PAYLOAD_MODEL = ClickPayload

    def __init__(self, dino_process: DinoProcessNode):
        self._dino_process = dino_process

    def handle(self, payload: ClickPayload) -> dict:
        self._dino_process.set_selection_click(payload.x, payload.y)
        return {"status": "ok"}
