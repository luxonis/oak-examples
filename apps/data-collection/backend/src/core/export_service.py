from core.neural_network.pipeline.model_state import ModelState
from core.base_service import BaseService
from core.service_name import ServiceName
from core.snapping.conditions.base_condition import Condition
from core.snapping.conditions.condition_key import ConditionKey


class ExportService(BaseService[None]):
    """Returns the current configuration state to the frontend."""

    NAME = ServiceName.EXPORT

    def __init__(
        self, model_state: ModelState, conditions: dict[ConditionKey, Condition]
    ):
        super().__init__()
        self._model_state: ModelState = model_state
        self._conditions: dict[ConditionKey, Condition] = conditions

    def export_conditions_config(self) -> dict[str, dict]:
        """
        Export current configuration of all conditions.
        """
        configs: dict[str, dict] = {}

        for key, condition in self._conditions.items():
            cfg = condition.export_config()
            if "cooldown" in cfg:
                cfg["cooldown"] = round(cfg["cooldown"] / 60.0, 1)

            configs[key.value] = cfg

        return configs

    def handle(self, payload: None = None) -> dict[str, any]:
        return {
            "classes": self._model_state.current_classes,
            "confidence_threshold": self._model_state.confidence_threshold,
            "snapping": {
                "running": any(cond.enabled for cond in self._conditions.values()),
                **self.export_conditions_config(),
            },
        }
