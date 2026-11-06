import enum
from dataclasses import dataclass

import depthai as dai


class DangerLevel(enum.Enum):
    SAFE = "SAFE"
    WARNING = "WARNING"
    DANGER = "DANGER"


class DangerSource(enum.Enum):
    SEGMENTATION = "SEGMENTATION"
    POINTCLOUD = "POINTCLOUD"


@dataclass(slots=True)
class DangerSpatialDetection:
    """Person track with normalized image box and ground-frame points in mm."""

    track_id: int
    bbox: tuple[float, float, float, float]
    closest_point_mm: tuple[float, float, float] | None
    centroid_point_mm: tuple[float, float, float] | None
    danger_zone: DangerLevel


class DangerClassification(dai.Buffer):
    """Smoothed alert level with person detections and contributing sources."""

    def __init__(self):
        super().__init__()
        self._level: DangerLevel = DangerLevel.SAFE
        self._danger_detections: list[DangerSpatialDetection] = []
        self._active_sources: list[DangerSource] = []

    @property
    def level(self) -> DangerLevel:
        return self._level

    @level.setter
    def level(self, value: DangerLevel):
        if not isinstance(value, DangerLevel):
            raise TypeError(f"level must be a DangerLevel, got {type(value).__name__}")
        self._level = value

    @property
    def danger_detections(self) -> list[DangerSpatialDetection]:
        return self._danger_detections

    @danger_detections.setter
    def danger_detections(self, value: list[DangerSpatialDetection]):
        self._danger_detections = list(value)

    @property
    def active_sources(self) -> list[DangerSource]:
        return self._active_sources

    @active_sources.setter
    def active_sources(self, value: list[DangerSource]):
        if any(not isinstance(source, DangerSource) for source in value):
            raise TypeError("active_sources must contain DangerSource values")
        self._active_sources = list(value)
