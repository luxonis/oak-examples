from typing import Optional
from pydantic import BaseModel, Field, RootModel
from core.snapping.conditions.condition_key import ConditionKey


class ConditionConfig(BaseModel):
    """Configuration of a single snapping condition."""

    enabled: bool = Field(default=True)
    cooldown: Optional[float] = Field(default=None, ge=0.0)
    interval: Optional[float] = Field(default=None, ge=0.0)
    threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    margin: Optional[float] = Field(default=None, ge=0.0)


class SnapPayload(RootModel[dict[ConditionKey, ConditionConfig]]):
    """Map of snapping conditions keyed by ConditionKey enum."""

    def to_dict(self) -> dict[ConditionKey, ConditionConfig]:
        return self.root
