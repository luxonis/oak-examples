from core.base_service import BaseService
from core.object_selection.selection_mask_node import SelectionMaskNode


class ClearSelectionService(BaseService[None]):
    NAME = "Clear Selection Service"
    PAYLOAD_MODEL = None

    def __init__(self, selection_node: SelectionMaskNode):
        self._selection_node = selection_node

    def handle_typed(self, payload: None) -> dict:
        self._selection_node.clear_selection()
        return {"ok": True}
