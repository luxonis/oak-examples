class SegmentationSelectionService:
    NAME = "BBox Prompt Service"

    def __init__(self, tracker):
        self.tracker = tracker

    def process(self, payload):
        bbox = payload.get("bbox")
        if bbox is None:
            self.tracker._logger.info("No bbox in payload")
            return {"status": "error"}

        x = bbox.get("x")
        y = bbox.get("y")
        if x is None or y is None:
            self.tracker._logger.info("No x/y in bbox")
            return {"status": "error"}
        self.tracker._logger.info(f"Received selection click at normalized coords: ({x}, {y})")
        self.tracker.set_selection_click(x, y)
        return {"status": "ok"}

    def clear(self, payload):
        self.tracker.clear_selection()
        return {"status": "ok"}
