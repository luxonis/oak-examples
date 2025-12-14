class ClickPromptService:
    NAME_CLICK = "Click Prompt Service"
    NAME_CLEAR = "Clear Click Prompt Service"

    def __init__(self, tracker):
        self.tracker = tracker

    def handle(self, payload: dict[str, any]):
        click = payload.get("click")
        if click is None:
            self.tracker._logger.info("No click in payload")
            return {"status": "error"}

        x = click.get("x")
        y = click.get("y")
        if x is None or y is None:
            self.tracker._logger.info("No x/y in click")
            return {"status": "error"}
        self.tracker._logger.info(f"Received selection click at normalized coords: ({x}, {y})")
        self.tracker.set_selection_click(x, y)
        return {"status": "ok"}

    def clear(self, payload):
        self.tracker.clear_selection()
        return {"status": "ok"}
