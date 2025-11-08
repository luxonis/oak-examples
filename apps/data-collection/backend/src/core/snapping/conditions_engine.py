from __future__ import annotations
from typing import Dict, Generator, Any

from core.front_end_services.payloads.snap_payload import ConditionConfig
from core.snapping.conditions.base_condition import Condition
from core.snapping.conditions.condition_key import ConditionKey


class ConditionsEngine:
    """
    Engine for managing and evaluating snap trigger conditions.
    """

    def __init__(self):
        self.conditions: Dict[ConditionKey, Condition] = {}

    def register(self, condition: Condition) -> None:
        """Register a condition instance (e.g., LowConfidenceCondition())."""
        key = condition.get_key()
        self.conditions[key] = condition

    def evaluate(self, **context: Any) -> Generator[Condition, None, None]:
        """
        Evaluate all enabled conditions.
        Returns an iterator of those that should trigger.
        Context may include: frame, det_data, tracklets, runtime, etc.
        """
        for cond in self.conditions.values():
            if not cond.enabled:
                continue
            if cond.should_trigger(**context):
                yield cond

    def import_conditions_config(self, config: Dict[str, ConditionConfig]) -> None:
        """
        Apply configuration dict to registered conditions.
        """
        for key, params in config.items():
            cond = self.conditions.get(key)
            if not cond:
                continue
            cond.apply_config(params)

    def export_conditions_config(self) -> Dict[str, dict]:
        """
        Export current configuration of all registered conditions.
        """
        configs: Dict[str, dict] = {}

        for key, condition in self.conditions.items():
            cfg = condition.export_config()
            if "cooldown" in cfg:
                cfg["cooldown"] = round(cfg["cooldown"] / 60.0, 1)

            configs[key.value] = cfg

        return configs

    def any_active(self) -> bool:
        """Return True if any condition is currently enabled."""
        return any(cond.enabled for cond in self.conditions.values())
