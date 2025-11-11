from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

from core.snapping.front_end_config_service.snap_payload import ConditionConfig
from core.snapping.conditions.condition_key import ConditionKey
from time import time


class Condition(ABC):
    """
    Abstract base class for all snap trigger conditions.

    Each condition encapsulates:
      - its unique KEY (class-level)
      - human-readable name and optional tags
      - configuration: enabled state, cooldown interval, etc.
    """

    KEY: ConditionKey  # must be defined in subclasses

    def __init__(
        self,
        name: str,
        default_cooldown: float,
        tags: Optional[List[str]] = None,
    ):
        if not getattr(self, "KEY", None):
            raise ValueError(f"{self.__class__.__name__} must define a KEY constant")

        self.__key = self.KEY
        self.name = name
        self.tags = tags or []
        self.enabled: bool = False
        self.cooldown: float = max(0.0, float(default_cooldown))
        self._last_trigger_time: Optional[float] = None

    @abstractmethod
    def should_trigger(self, *args, **kwargs) -> bool:
        """Return True if this condition should trigger."""
        pass

    @abstractmethod
    def make_extras(self, *args, **kwargs) -> Dict[str, str]:
        """Return optional metadata attached to the snap."""
        pass

    def apply_config(self, conf: ConditionConfig):
        self.enabled = conf.enabled
        if not self.enabled:
            self.reset_cooldown()
        self.cooldown = conf.cooldown

    def export_config(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "cooldown": self.cooldown,
        }

    def get_key(self) -> ConditionKey:
        return self.__key

    def reset_cooldown(self):
        """Reset internal cooldown tracking."""
        self._last_trigger_time = None

    def _cooldown_passed(self) -> bool:
        """Return True if enough time passed since the last trigger."""
        now = time()
        if self._last_trigger_time is None:
            return True
        return (now - self._last_trigger_time) >= self.cooldown

    def mark_triggered(self):
        """Record that this condition has just fired."""
        now = time()
        self._last_trigger_time = now
