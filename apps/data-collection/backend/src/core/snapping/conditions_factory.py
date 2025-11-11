import importlib

from box import Box

from core.snapping.conditions.condition_key import ConditionKey
from core.snapping.conditions.base_condition import Condition


class ConditionsFactory:
    @staticmethod
    def build_conditions_from_yaml(
        conditions_yaml: Box,
    ) -> dict[ConditionKey, Condition]:
        conditions: dict[ConditionKey, Condition] = {}

        for entry in conditions_yaml.conditions:
            if not entry.path:
                continue

            try:
                module_name, class_name = entry.path.rsplit(".", 1)
                module = importlib.import_module(module_name)
                cls = getattr(module, class_name)
                cond: Condition = cls(
                    name=entry.name,
                    default_cooldown=conditions_yaml.cooldown,
                    tags=entry.tags,
                )
                conditions[cond.get_key()] = cond
            except Exception as e:
                print(f"Failed to import condition {entry.path}: {e}")

        return conditions
