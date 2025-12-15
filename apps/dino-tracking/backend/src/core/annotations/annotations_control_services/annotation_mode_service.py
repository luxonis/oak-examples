from core.base_service import BaseService
from core.annotations.dino_annotation_node import DinoAnnotationNode
from pydantic import BaseModel, ValidationError
from typing import Literal


class AnnotationModePayload(BaseModel):
    mode: Literal["heatmap", "bbox"]


class AnnotationModeService(BaseService[AnnotationModePayload]):
    NAME = "Annotation Mode Service"

    def __init__(self, annotations_node: DinoAnnotationNode):
        self._annotations_node = annotations_node

    def handle(self, payload) -> dict:
        try:
            payload = AnnotationModePayload.model_validate(payload)
        except ValidationError as e:
            self._annotations_node._logger.info(f"Validation error in AnnotationModeService:{e}")
            return {"ok": False, "error": e.errors()}

        self._annotations_node.set_mode(payload.mode)
        return {
            "ok": True,
            "annotation_mode": self._annotations_node.get_mode(),
        }