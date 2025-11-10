from core.snapping.conditions.base_condition import Condition
from core.snapping.conditions.condition_key import ConditionKey
from typing import Dict


class TimedCondition(Condition):
    """Triggers snaps at regular time intervals."""

    KEY = ConditionKey.TIMED

    def __init__(self, name: str, default_cooldown: float, tags: list[str]):
        super().__init__(name, default_cooldown, tags or [])

    def should_trigger(self, **kwargs) -> bool:
        if self.enabled and self._cooldown_passed():
            self.mark_triggered()
            return True
        return False

    def make_extras(self) -> Dict[str, str]:
        return {"reason": "timed_snap"}
