from core.annotations.dino_annotation_node import DinoAnnotationNode
from core.annotations.outlines_overlay_node import OutlinesOverlayNode
from core.base_service import BaseService
from core.detections_tracking.heatmap_to_detections_node import HeatmapToDetectionsNode


class StateService(BaseService[None]):
    NAME = "BE State Service"
    PAYLOAD_MODEL = None

    def __init__(
        self,
        heatmap_det: HeatmapToDetectionsNode,
        annotations_node: DinoAnnotationNode,
        outlines_node: OutlinesOverlayNode,
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
