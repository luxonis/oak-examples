from typing import Callable

from nn import NNState


class GetCurrentParamsService:
    """
    Service that returns current parameters for the frontend.
    Matches the expected format: class_names, image_prompt_labels, confidence_threshold.
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
            "image_prompt_labels": nn_state.image_prompt_labels,
            "confidence_threshold": nn_state.confidence_threshold,
        }
