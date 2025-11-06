from typing import TypedDict, Optional
from core.snapping.conditions.condition_key import ConditionKey


class ConditionConfig(TypedDict, total=False):
    """Configuration of a single snapping condition."""

    enabled: bool
    cooldown: Optional[float]
    interval: Optional[float]
    threshold: Optional[float]
    margin: Optional[float]


SnapPayload = dict[ConditionKey, ConditionConfig]
