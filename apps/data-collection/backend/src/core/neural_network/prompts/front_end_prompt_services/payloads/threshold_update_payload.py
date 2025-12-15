from pydantic import BaseModel, Field


class ThresholdUpdatePayload(BaseModel):
    """Payload for updating NN confidence threshold."""

    threshold: float = Field(..., ge=0.0, le=1.0)
