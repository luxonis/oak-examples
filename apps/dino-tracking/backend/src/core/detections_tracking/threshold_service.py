from core.base_service import BaseService
from core.detections_tracking.heatmap_detection_node import HeatmapDetectionNode
from pydantic import BaseModel, Field, ValidationError


class ThresholdUpdatePayload(BaseModel):
    threshold: float = Field(..., ge=0.0, le=1.0)


class ThresholdService(BaseService[ThresholdUpdatePayload]):
    NAME = "Threshold Update Service"

    def __init__(self, heatmap_det: HeatmapDetectionNode):
        self._heatmap_det = heatmap_det

    def handle(self, payload) -> dict:
        try:
            payload = ThresholdUpdatePayload.model_validate(payload)
        except ValidationError as e:
            self._heatmap_det._logger.info(f"Validation error in ThresholdService:{e}")
            return {"ok": False, "error": e.errors()}
        self._heatmap_det._logger.info(
            f"Updating confidence threshold to {payload.threshold}"
        )
        self._heatmap_det.set_confidence_threshold(payload.threshold)
        return {
            "ok": True,
            "confidence": self._heatmap_det.get_confidence_threshold(),
        }
