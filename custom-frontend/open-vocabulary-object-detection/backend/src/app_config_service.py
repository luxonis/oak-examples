from typing import Callable

from nn import NNState


class GetAppConfigService:
    """
    Service that aggregates current app state for the frontend.
    Returns NN state (classes, confidence threshold).
    """

    def __init__(
        self,
        get_nn_state: Callable[[], NNState],
    ):
        self._get_nn_state = get_nn_state

    def handle(self, _req=None) -> dict:
        nn_state = self._get_nn_state()
        return {
            "class_names": nn_state.current_classes,
            "confidence_threshold": nn_state.confidence_threshold,
        }
