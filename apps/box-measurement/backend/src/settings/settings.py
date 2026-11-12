from pydantic import BaseModel, Field


class Settings(BaseModel):
    fps: int = Field(20, ge=5, le=30)
    detection_confidence_threshold: float = Field(0.5, ge=0.0, le=1.0)
    continuous_recording_enabled: bool = True
    continuous_recording_chunk_length_sec: int = Field(150, gt=0)
    continuous_recording_max_storage_gb: float = Field(20.0, gt=0)


class SetDetectionConfidenceThresholdRequest(BaseModel):
    threshold: float = Field(ge=0.0, le=1.0)


class SetSupportPlaneDistanceOffsetRequest(BaseModel):
    offset_mm: float = Field(ge=-100.0, le=100.0)
