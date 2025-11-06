import importlib

from box import Box

from core.snapping.conditions_engine import ConditionsEngine
from core.snapping.conditions.base_condition import Condition


class ConditionsFactory:
    def __init__(self, conditions_yaml: Box):
        self._conditions_yaml = conditions_yaml

        self._engine: ConditionsEngine = self._build_engine()

    def _build_engine(self) -> ConditionsEngine:
        engine = ConditionsEngine()

        for entry in self._conditions_yaml.conditions:
            if not entry.path:
                continue

            try:
                module_name, class_name = entry.path.rsplit(".", 1)
                module = importlib.import_module(module_name)
                cls = getattr(module, class_name)
                cond: Condition = cls(
                    name=entry.name,
                    default_cooldown=self._conditions_yaml.cooldown,
                    tags=entry.tags,
                )
                engine.register(cond)
            except Exception as e:
                print(f"[WARN] Failed to import condition {entry.path}: {e}")

        return engine

    def get_engine(self) -> ConditionsEngine:
        return self._engine
