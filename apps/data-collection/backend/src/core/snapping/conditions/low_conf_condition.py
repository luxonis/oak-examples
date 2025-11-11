from core.snapping.front_end_config_service.snap_payload import ConditionConfig
from core.snapping.conditions.base_condition import Condition
from core.snapping.conditions.condition_key import ConditionKey
from typing import Dict, Any
import depthai as dai


class LowConfidenceCondition(Condition):
    """Triggers when any detection has confidence below a threshold."""

    KEY = ConditionKey.LOW_CONFIDENCE

    def __init__(self, name: str, default_cooldown: float, tags: list[str]):
        super().__init__(name, default_cooldown, tags or [])
        self.threshold: float = 0.3
        self.last_lowest: float = 0.0

    def apply_config(self, conf: ConditionConfig):
        super().apply_config(conf)
        if conf.threshold:
            val = float(conf.threshold)
            self.threshold = max(0.0, min(1.0, val))

    def export_config(self) -> Dict[str, Any]:
        base = super().export_config()
        base["threshold"] = self.threshold
        return base

    def should_trigger(self, detections: list[dai.ImgDetection], **kwargs) -> bool:
        if self.enabled and self._cooldown_passed():
            if self._check_detections(detections):
                self.mark_triggered()
                return True
        return False

    def _check_detections(self, detections: list[dai.ImgDetection]) -> bool:
        if not detections:
            return False
        self.last_lowest = min((float(d.confidence) for d in detections), default=1.0)
        return self.last_lowest < self.threshold

    def make_extras(self) -> Dict[str, str]:
        return {
            "reason": "low_confidence",
            "threshold": f"{round(self.threshold, 3)}",
            "min_conf": f"{round(self.last_lowest, 3)}",
        }
