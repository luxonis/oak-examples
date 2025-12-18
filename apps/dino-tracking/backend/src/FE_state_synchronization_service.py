from annotations.detections_annotation_overlay_node import DetectionsAnnotationOverlay
from annotations.outlines_overlay_node import OutlinesOverlay
from base_service import BaseService
from detections_tracking.heatmap_to_detections_node import HeatmapToDetections


class FEStateSynchronization(BaseService[None]):
    NAME = "BE State Service"
    PAYLOAD_MODEL = None

    def __init__(
        self,
        heatmap_det: HeatmapToDetections,
        annotations_node: DetectionsAnnotationOverlay,
        outlines_node: OutlinesOverlay,
    ):
        self._heatmap_det = heatmap_det
        self._annotations_node = annotations_node
        self._outlines_node = outlines_node

    def handle_typed(self, payload: None) -> dict:
        return {
            "ok": True,
            "confidence": self._heatmap_det.get_confidence_threshold(),
            "annotation_mode": self._annotations_node.get_mode(),
            "outlines": self._outlines_node.get_active(),
        }
