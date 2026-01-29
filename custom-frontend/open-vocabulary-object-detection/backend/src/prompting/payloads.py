from pydantic import BaseModel, Field


class ClassUpdatePayload(BaseModel):
    """Payload for updating detection classes."""

    classes: list[str] = Field(..., min_length=1, description="List of class names")


class ThresholdUpdatePayload(BaseModel):
    """Payload for updating NN confidence threshold."""

    threshold: float = Field(..., ge=0.0, le=1.0)


class ImageUploadPayload(BaseModel):
    """Payload for uploading an image from the frontend."""

    filename: str = Field(..., min_length=1)
    type: str = Field(..., min_length=1)
    data: str = Field(..., description="Base64-encoded image data")


class BBoxPromptPayload(BaseModel):
    """Payload for bounding box region selection."""

    x: float = Field(..., ge=0.0, le=1.0, description="Normalized x coordinate [0-1]")
    y: float = Field(..., ge=0.0, le=1.0, description="Normalized y coordinate [0-1]")
    width: float = Field(..., gt=0.0, le=1.0, description="Normalized width [0-1]")
    height: float = Field(..., gt=0.0, le=1.0, description="Normalized height [0-1]")
