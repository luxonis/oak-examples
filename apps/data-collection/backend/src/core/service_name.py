from enum import Enum


class ServiceName(str, Enum):
    """Unique identifiers for all backend services."""

    CLASS_UPDATE = "Class Update Service"
    THRESHOLD_UPDATE = "Threshold Update Service"
    IMAGE_UPLOAD = "Image Upload Service"
    SNAP_COLLECTION = "Snap Collection Service"
    BBOX_PROMPT = "BBox Prompt Service"
    EXPORT = "Export Service"
