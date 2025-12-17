from core.base_service import BaseService
from core.annotations.dino_annotation_node import DinoAnnotationNode
from core.annotations.outlines_overlay_node import OutlinesOverlayNode
from core.detections_tracking.heatmap_to_bounding_box_node import (
    HeatmapToBoundingBoxNode,
)


class StateService(BaseService[None]):
    NAME = "BE State Service"
    PAYLOAD_MODEL = None

    def __init__(
        self,
        heatmap_det: HeatmapToBoundingBoxNode,
        annotations_node: DinoAnnotationNode,
        outlines_node: OutlinesOverlayNode,
    ):
        self.heatmap_det = heatmap_det
        self.annotations_node = annotations_node
        self.outlines_node = outlines_node

    def handle_typed(self, payload: None) -> dict:
        return {
            "ok": True,
            "confidence": self.heatmap_det.get_confidence_threshold(),
            "annotation_mode": self.annotations_node.get_mode(),
            "outlines": self.outlines_node.get_active(),
        }
