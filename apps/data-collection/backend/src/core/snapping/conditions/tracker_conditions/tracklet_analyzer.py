from __future__ import annotations
from typing import Optional, Tuple, Dict
import depthai as dai


class TrackletAnalyzer:
    """
    Provides safe, normalized access to dai.Tracklet properties
    """

    def __init__(self, tracklet: dai.Tracklet):
        self._t = tracklet

    @property
    def id(self) -> Optional[int]:
        try:
            tid = int(getattr(self._t, "id", -1))
            return tid if tid >= 0 else None
        except Exception:
            return None

    @property
    def is_tracked(self) -> bool:
        val = getattr(self._t, "status", None)
        try:
            return val == dai.Tracklet.TrackingStatus.TRACKED
        except Exception:
            try:
                return int(val) == 1
            except Exception:
                return False

    @property
    def is_lost(self) -> bool:
        val = getattr(self._t, "status", None)
        try:
            return val == dai.Tracklet.TrackingStatus.LOST
        except Exception:
            try:
                return int(val) == 2
            except Exception:
                return False

    def center_area(self) -> Optional[Tuple[float, float, float]]:
        """
        Return (cx, cy, area_norm) in normalized coordinates.
        """
        roi = getattr(self._t, "roi", None)
        if roi is not None:
            try:
                tl = roi.topLeft()
                br = roi.bottomRight()
                x0, y0 = float(tl.x), float(tl.y)
                x1, y1 = float(br.x), float(br.y)
                cx, cy = 0.5 * (x0 + x1), 0.5 * (y0 + y1)
                area = max(0.0, (x1 - x0) * (y1 - y0))
                return cx, cy, area
            except Exception:
                pass

        det = getattr(self._t, "srcImgDetection", None)
        if det is not None:
            x = float(getattr(det, "x", getattr(det, "xmin", 0.0)))
            y = float(getattr(det, "y", getattr(det, "ymin", 0.0)))
            w = float(getattr(det, "width", 0.0))
            h = float(getattr(det, "height", 0.0))
            cx, cy = x + 0.5 * w, y + 0.5 * h
            return cx, cy, max(0.0, w * h)

        return None

    def was_tracked(self, prev_state: Dict[int, bool]) -> bool:
        tid = self.id
        return tid is not None and prev_state.get(tid, False)

    def update_state(self, state: Dict[int, bool]):
        tid = self.id
        if tid is not None:
            state[tid] = self.is_tracked
