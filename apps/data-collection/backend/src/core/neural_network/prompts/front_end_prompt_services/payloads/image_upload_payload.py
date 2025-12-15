from pydantic import BaseModel, Field


class ImageUploadPayload(BaseModel):
    """Payload for uploading an image from the frontend."""

    filename: str = Field(..., min_length=1)
    type: str = Field(..., min_length=1)
    data: str = Field(..., description="Base64-encoded image data")
