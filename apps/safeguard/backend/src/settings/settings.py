"""Runtime configuration for the SafeGuard example (never written to disk)."""

import os
from pydantic import BaseModel, Field, model_validator


class SpatialZone(BaseModel):
    """Horizontal zone in ground-aligned camera coordinates, in millimeters.

    The zone spans ``x_min_mm`` to ``x_max_mm`` and extends forward through
    ``distance_mm``. Its height is unrestricted.
    """

    distance_mm: float = Field(gt=0)
    x_min_mm: float
    x_max_mm: float

    @model_validator(mode="after")
    def validate_order(self) -> "SpatialZone":
        if self.x_min_mm >= self.x_max_mm:
            raise ValueError("x_min_mm must be less than x_max_mm")
        return self


class Settings(BaseModel):
    """Live pipeline settings; changes rebuild the pipeline without persistence."""

    fps: int = Field(30, ge=10, le=30)
    generic_object_detection_enabled: bool = False
    awareness_escalation_sec: int = Field(5, gt=0)
    deescalation_sec: int = Field(5, gt=0)
    danger_roi: SpatialZone = Field(
        default_factory=lambda: SpatialZone(
            distance_mm=1000, x_min_mm=-500, x_max_mm=500
        )
    )
    warning_roi: SpatialZone = Field(
        default_factory=lambda: SpatialZone(
            distance_mm=2000, x_min_mm=-1000, x_max_mm=1000
        )
    )

    @model_validator(mode="after")
    def validate_threshold_order(self) -> "Settings":
        if self.danger_roi.distance_mm >= self.warning_roi.distance_mm:
            raise ValueError("danger distance must be less than warning distance")
        return self

    @classmethod
    def from_env(cls) -> "Settings":
        """Read a small set of SAFEGUARD_* variables once at startup."""
        scalar_vars = {
            "fps": "FPS",
            "generic_object_detection_enabled": "GENERIC_OBSTACLES",
            "awareness_escalation_sec": "AWARENESS_ESCALATION_SEC",
            "deescalation_sec": "DEESCALATION_SEC",
        }
        values = {
            field: os.environ[f"SAFEGUARD_{suffix}"]
            for field, suffix in scalar_vars.items()
            if f"SAFEGUARD_{suffix}" in os.environ
        }
        for field, prefix in (("danger_roi", "DANGER"), ("warning_roi", "WARNING")):
            zone_vars = {
                key: os.environ[f"SAFEGUARD_{prefix}_{suffix}"]
                for key, suffix in (
                    ("distance_mm", "DISTANCE_MM"),
                    ("x_min_mm", "X_MIN_MM"),
                    ("x_max_mm", "X_MAX_MM"),
                )
                if f"SAFEGUARD_{prefix}_{suffix}" in os.environ
            }
            if zone_vars:
                defaults = getattr(cls(), field).model_dump()
                values[field] = defaults | zone_vars
        return cls.model_validate(values)
