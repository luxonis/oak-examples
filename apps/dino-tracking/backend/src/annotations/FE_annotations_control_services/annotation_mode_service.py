from typing import Literal

from pydantic import BaseModel, ValidationError

from annotations.detections_annotation_overlay_node import DetectionsAnnotationOverlay
from base_service import BaseService


class AnnotationModePayload(BaseModel):
    mode: Literal["heatmap", "bbox"]


class AnnotationMode(BaseService[AnnotationModePayload]):
    NAME = "Annotation Mode Service"
    PAYLOAD_MODEL = AnnotationModePayload

    def __init__(self, annotations_node: DetectionsAnnotationOverlay):
        self._annotations_node = annotations_node

    def on_validation_error(self, e: ValidationError) -> None:
        self._annotations_node._logger.info(
            f"Validation error in AnnotationModeService: {e}"
        )

    def handle_typed(self, payload: AnnotationModePayload) -> dict:
        self._annotations_node.set_mode(payload.mode)
        return {
            "ok": True,
            "annotation_mode": self._annotations_node.get_mode(),
        }
