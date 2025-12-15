from core.annotations.dino_annotation_node import DinoAnnotationNode
from core.annotations.outlines_overlay_node import OutlinesOverlayNode
from core.detections_tracking.heatmap_detection_node import HeatmapDetectionNode


class StateService:

    NAME = "BE State Service"

    def __init__(self, heatmap_det: HeatmapDetectionNode, annotations_node: DinoAnnotationNode,  outlines_node: OutlinesOverlayNode):
        self.heatmap_det = heatmap_det
        self.annotations_node = annotations_node
        self.outlines_node = outlines_node

    def handle(self, payload: str = None) -> dict[str, str | float]:
        return {
            "confidence": self.heatmap_det.get_confidence_threshold(),
            "annotation_mode": self.annotations_node.get_mode(),
            "outlines": self.outlines_node.get_active(),
        }
