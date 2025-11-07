from core.neural_network.pipeline.model_state import ModelState
from core.services.base_service import BaseService
from core.services.service_name import ServiceName
from core.snapping.conditions_engine import ConditionsEngine


class ExportService(BaseService[None]):
    """Returns the current configuration state to the frontend."""

    NAME = ServiceName.EXPORT

    def __init__(self, model_state: ModelState, condition_engine: ConditionsEngine):
        super().__init__()
        self._model_state: ModelState = model_state
        self._condition_engine: ConditionsEngine = condition_engine

    def handle(self, payload: None = None) -> dict[str, any]:
        return {
            "classes": self._model_state.current_classes,
            "confidence_threshold": self._model_state.confidence_threshold,
            "snapping": {
                "running": self._condition_engine.any_active(),
                **self._condition_engine.export_conditions_config(),
            },
        }
