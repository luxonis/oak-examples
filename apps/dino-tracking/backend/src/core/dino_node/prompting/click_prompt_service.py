from core.dino_node.dino_process_node import DinoProcessNode


class ClickPromptService:
    NAME_CLICK = "Click Prompt Service"
    NAME_CLEAR = "Clear Click Prompt Service"

    def __init__(self, dino_process: DinoProcessNode):
        self._dino_process = dino_process

    def handle(self, payload: dict[str, any]):
        click = payload.get("click")
        if click is None:
            return {"status": "error"}

        x = click.get("x")
        y = click.get("y")
        if x is None or y is None:
            return {"status": "error"}
        self._dino_process.set_selection_click(x, y)
        return {"status": "ok"}

    def clear(self, payload):
        self._dino_process.clear_selection()
        return {"status": "ok"}
