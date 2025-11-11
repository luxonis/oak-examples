from pydantic import BaseModel, Field


class BBoxPromptPayload(BaseModel):
    x: float = Field(..., ge=0.0, le=1.0, description="Normalized x coordinate [0–1]")
    y: float = Field(..., ge=0.0, le=1.0, description="Normalized y coordinate [0–1]")
    width: float = Field(..., gt=0.0, le=1.0, description="Normalized width [0–1]")
    height: float = Field(..., gt=0.0, le=1.0, description="Normalized height [0–1]")
