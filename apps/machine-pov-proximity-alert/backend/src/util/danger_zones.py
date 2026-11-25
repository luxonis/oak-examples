"""Shared severity ordering and ground-aligned spatial zone checks."""

import math
from collections.abc import Iterable

from depthai_pipeline.common.message.danger_classification import DangerLevel
from depthai_pipeline.pointcloud_object_detection.message import Obstacle
from settings.settings import SpatialZone

_SEVERITY = {
    DangerLevel.SAFE: 0,
    DangerLevel.WARNING: 1,
    DangerLevel.DANGER: 2,
}


def level_severity(level: DangerLevel) -> int:
    return _SEVERITY[level]


def is_more_severe(candidate: DangerLevel, reference: DangerLevel) -> bool:
    return level_severity(candidate) > level_severity(reference)


def is_at_least_as_severe(
    candidate: DangerLevel,
    reference: DangerLevel,
) -> bool:
    return level_severity(candidate) >= level_severity(reference)


def classify_point(
    x_mm: float,
    z_mm: float,
    danger_zone: SpatialZone,
    warning_zone: SpatialZone,
) -> DangerLevel:
    """Classify a ground-frame horizontal point against the two zones.

    Args:
        x_mm: Horizontal offset from camera center, in millimeters.
        z_mm: Forward distance in millimeters.
        danger_zone: Inner, higher-severity zone.
        warning_zone: Outer zone.

    Returns:
        DANGER, WARNING, or SAFE. Non-finite coordinates are SAFE.
    """
    if not math.isfinite(x_mm) or not math.isfinite(z_mm):
        return DangerLevel.SAFE
    if (
        z_mm <= danger_zone.distance_mm
        and danger_zone.x_min_mm <= x_mm <= danger_zone.x_max_mm
    ):
        return DangerLevel.DANGER
    if (
        z_mm <= warning_zone.distance_mm
        and warning_zone.x_min_mm <= x_mm <= warning_zone.x_max_mm
    ):
        return DangerLevel.WARNING
    return DangerLevel.SAFE


def classify_obstacle(
    obstacle: Obstacle,
    danger_zone: SpatialZone,
    warning_zone: SpatialZone,
) -> DangerLevel:
    point = obstacle.nearest_point_xyz
    return classify_point(
        x_mm=float(point[0]),
        z_mm=float(point[2]),
        danger_zone=danger_zone,
        warning_zone=warning_zone,
    )


def max_level(levels: Iterable[DangerLevel]) -> DangerLevel:
    return max(levels, key=level_severity, default=DangerLevel.SAFE)
