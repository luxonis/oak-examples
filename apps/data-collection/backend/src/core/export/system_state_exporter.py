from typing import Dict, Any
from core.snapping.conditions_engine import ConditionsEngine
from core.model_state import ModelState


class SystemStateExporter:
    """
    Builds a full frontend-friendly snapshot of the current system configuration.
    """

    def __init__(
        self,
        model_state: ModelState,
        condition_engine: ConditionsEngine,
    ):
        self._model_state = model_state
        self._condition_engine = condition_engine

    def export_config(self) -> Dict[str, Any]:
        """
        Construct the unified configuration dictionary expected by the frontend.
        """
        return {
            "classes": self._model_state.get_classes(),
            "confidence_threshold": self._model_state.get_threshold(),
            "snapping": {
                "running": self._condition_engine.any_active(),
                **self._condition_engine.export_conditions_config(),
            },
        }
