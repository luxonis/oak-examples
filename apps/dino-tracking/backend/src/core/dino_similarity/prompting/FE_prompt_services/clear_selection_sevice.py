from core.base_service import BaseService
from core.dino_similarity.dino_selection_node import DinoSelectionNode


class ClearSelectionService(BaseService[None]):
    NAME = "Clear Selection Service"

    def __init__(self, dino_process: DinoSelectionNode):
        self._dino_process = dino_process

    def handle(self, payload=None) -> dict:
        self._dino_process._logger.info("Clearing selection via ClearSelectionService")
        self._dino_process.clear_selection()
        return {"status": "ok"}
