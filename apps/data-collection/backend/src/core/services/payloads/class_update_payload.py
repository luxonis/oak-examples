from pydantic import BaseModel, Field


class ClassUpdatePayload(BaseModel):
    """Payload for updating detection classes."""

    classes: list[str] = Field(..., min_length=1, description="List of class names")
