from base_service import BaseService
from object_selection.mask_selection_node import MaskSelection


class ClearSelectionPrompt(BaseService[None]):
    NAME = "Clear Selection Service"
    PAYLOAD_MODEL = None

    def __init__(self, selection_node: MaskSelection):
        self._selection_node = selection_node

    def handle_typed(self, payload: None) -> dict:
        self._selection_node.clear_selection()
        return {"ok": True}
