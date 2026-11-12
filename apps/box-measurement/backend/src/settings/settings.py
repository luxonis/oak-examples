from pydantic import BaseModel, Field, model_validator


class Settings(BaseModel):
    fps: int = Field(20, ge=5, le=30)
    detection_confidence_threshold: float = Field(0.5, ge=0.0, le=1.0)
    event_saving_enabled: bool = True
    save_failed_events: bool = True
    event_storage_max_gb: float = Field(5.0, gt=0)
    event_video_pre_trigger_sec: int = Field(5, ge=0)
    event_video_duration_sec: int = Field(15, gt=0)
    continuous_recording_enabled: bool = True
    continuous_recording_chunk_length_sec: int = Field(150, gt=0)
    continuous_recording_max_storage_gb: float = Field(20.0, gt=0)

    @model_validator(mode="after")
    def validate_video_durations(self) -> "Settings":
        if self.event_video_duration_sec <= self.event_video_pre_trigger_sec:
            raise ValueError(
                "event_video_duration_sec must be greater than "
                "event_video_pre_trigger_sec"
            )

        return self


class SetDetectionConfidenceThresholdRequest(BaseModel):
    threshold: float = Field(ge=0.0, le=1.0)


class SetSupportPlaneDistanceOffsetRequest(BaseModel):
    offset_mm: float = Field(ge=-100.0, le=100.0)
