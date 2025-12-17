from core.base_service import BaseService
from core.detections_tracking.heatmap_to_detections_node import (
    HeatmapToDetectionsNode,
)
from pydantic import BaseModel, Field, ValidationError


class ThresholdUpdatePayload(BaseModel):
    threshold: float = Field(..., ge=0.0, le=1.0)


class ThresholdService(BaseService[ThresholdUpdatePayload]):
    NAME = "Threshold Update Service"
    PAYLOAD_MODEL = ThresholdUpdatePayload

    def __init__(self, heatmap_det: HeatmapToDetectionsNode):
        self._heatmap_det = heatmap_det

    def on_validation_error(self, e: ValidationError) -> None:
        self._heatmap_det._logger.warning(f"Validation error in ThresholdService: {e}")

    def handle_typed(self, payload: ThresholdUpdatePayload) -> dict:
        self._heatmap_det.set_confidence_threshold(payload.threshold)
        return {
            "ok": True,
            "confidence": self._heatmap_det.get_confidence_threshold(),
        }
