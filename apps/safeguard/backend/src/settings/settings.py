"""Runtime configuration for the machine-mounted proximity alert example."""

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
