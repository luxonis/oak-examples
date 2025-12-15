from core.snapping.conditions.base_condition import Condition
from core.snapping.conditions.condition_key import ConditionKey
from typing import Dict
import depthai as dai


class NoDetectionsCondition(Condition):
    """Triggers when no objects are detected in the current frame."""

    KEY = ConditionKey.NO_DETECTIONS

    def __init__(self, name: str, default_cooldown: float, tags: list[str]):
        super().__init__(name, default_cooldown, tags or [])

    def should_trigger(self, detections: list[dai.ImgDetection], **kwargs) -> bool:
        if self.enabled and self._cooldown_passed():
            if not detections or len(detections) == 0:
                self.mark_triggered()
                return True
        return False

    def make_extras(self) -> Dict[str, str]:
        return {"reason": "no_detections"}
