class ClickState:
    """
    Stores a pending click from FE until it is processed
    inside the node's process() loop.
    """

    def __init__(self):
        self._pending_click: tuple[float, float] | None = None

    def set_click(self, x_norm: float, y_norm: float) -> None:
        self._pending_click = (x_norm, y_norm)

    def clear(self) -> None:
        self._pending_click = None

    def consume_click(self) -> tuple[float, float] | None:
        click = self._pending_click
        self._pending_click = None
        return click
