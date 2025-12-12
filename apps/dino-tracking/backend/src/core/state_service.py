from core.annotations.dino_annotation_node import DinoAnnotationNode
from core.annotations.outlines_overlay_node import OutlinesOverlayNode


class StateService:

    NAME = "BE State Service"

    def __init__(self, annotation_node: DinoAnnotationNode, outlines_node: OutlinesOverlayNode):
        self.annotation_node = annotation_node
        self.outlines_node = outlines_node

    def handle(self, payload: str = None) -> dict[str, str | float]:
        self.annotation_node._logger.info("StateService: Providing current configuration state")
        return {
            "confidence": self.annotation_node.get_confidence(),
            "annotation_mode": self.annotation_node.get_mode(),
            "outlines": self.outlines_node.get_active(),
        }
