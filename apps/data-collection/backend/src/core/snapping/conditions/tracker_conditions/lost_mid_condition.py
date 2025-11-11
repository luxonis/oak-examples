from core.snapping.front_end_config_service.snap_payload import ConditionConfig
from core.snapping.conditions.base_condition import Condition
from core.snapping.conditions.tracker_conditions.tracklet_analyzer import (
    TrackletAnalyzer,
)
from core.snapping.conditions.condition_key import ConditionKey
from typing import Dict, Any
import depthai as dai


class LostMidCondition(Condition):
    """Triggers when an object is lost inside the frame center region."""

    KEY = ConditionKey.LOST_MID

    def __init__(self, name: str, default_cooldown: float, tags: list[str]):
        super().__init__(name, default_cooldown, tags or [])
        self.margin: float = 0.2
        self.prev_tracked: dict[int, bool] = {}

    def apply_config(self, conf: ConditionConfig):
        super().apply_config(conf)
        if conf.margin:
            val = float(conf.margin)
            self.margin = max(0.0, min(0.49, val))

    def export_config(self) -> Dict[str, Any]:
        base = super().export_config()
        base["margin"] = self.margin
        return base

    def should_trigger(self, tracklets: dai.Tracklet, **kwargs) -> bool:
        if self.enabled and self._cooldown_passed():
            if self._check_tracklets(tracklets):
                self.mark_triggered()
                return True
        return False

    def _check_tracklets(self, tracklets) -> bool:
        if tracklets is None:
            return False

        triggered = False
        for t in getattr(tracklets, "tracklets", []):
            tr = TrackletAnalyzer(t)
            if tr.is_lost and tr.was_tracked(self.prev_tracked):
                rc = tr.center_area()
                if rc is not None:
                    cx, cy, _ = rc
                    if (
                        self.margin <= cx <= 1 - self.margin
                        and self.margin <= cy <= 1 - self.margin
                    ):
                        triggered = True
            tr.update_state(self.prev_tracked)

        return triggered

    def make_extras(self) -> Dict[str, str]:
        return {"reason": "lost_in_middle", "margin": f"{round(self.margin, 3)}"}
