from typing import TypedDict


class ImageUploadPayload(TypedDict):
    """Payload for uploading an image from the frontend."""

    filename: str
    type: str
    data: str
