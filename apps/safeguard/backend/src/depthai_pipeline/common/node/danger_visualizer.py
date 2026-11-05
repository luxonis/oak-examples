import math

import depthai as dai
from depthai_nodes.utils.annotation_helper import AnnotationHelper

from depthai_pipeline.common.message.danger_classification import (
    DangerClassification,
    DangerLevel,
    DangerSource,
    DangerSpatialDetection,
)


class DangerVisualizer(dai.node.HostNode):
    """Draw alert state and tracked-person annotations on the RGB preview."""

    _COLOR_DANGER = (255, 0, 0, 1.0)
    _COLOR_WARNING = (255, 180, 0, 1.0)
    _COLOR_SAFE = (0, 200, 0, 1.0)

    _FILL_DANGER = (255, 0, 0, 0.15)
    _FILL_WARNING = (255, 180, 0, 0.15)
    _FILL_SAFE = (0, 200, 0, 0.15)

    _STATE_STYLE = {
        DangerLevel.WARNING: (_COLOR_WARNING, _FILL_WARNING),
        DangerLevel.DANGER: (_COLOR_DANGER, _FILL_DANGER),
    }
    _STATE_BORDER_THICKNESS = 4.0
    _STATE_LABEL = {
        DangerLevel.WARNING: "Warning",
        DangerLevel.DANGER: "Danger",
    }
    _SOURCE_LABEL = {
        DangerSource.SEGMENTATION: "Person",
        DangerSource.POINTCLOUD: "Point Cloud",
    }
    _STATE_LABEL_POSITION = (0.02, 0.07)
    _STATE_LABEL_SIZE = 48
    _BOX_THICKNESS = 2.0

    def __init__(self) -> None:
        super().__init__()
        self._displayed_sources: list[DangerSource] = []

    def build(
        self,
        classifications: dai.Node.Output,
    ) -> "DangerVisualizer":
        self.link_args(classifications)
        self._displayed_sources = []
        return self

    def _get_displayed_sources(
        self,
        classification: DangerClassification,
    ) -> list[DangerSource]:
        """Keep source labels visible until the current alert clears to SAFE."""
        if classification.level == DangerLevel.SAFE:
            self._displayed_sources = []
            return []

        for source in classification.active_sources:
            if source not in self._displayed_sources:
                self._displayed_sources.append(source)

        return list(self._displayed_sources)

    def _get_detection_style(
        self,
        track_visualization: DangerSpatialDetection,
    ) -> tuple[
        tuple[float, float, float, float],
        tuple[float, float, float, float],
    ]:
        level = track_visualization.danger_zone
        if level == DangerLevel.DANGER:
            return self._COLOR_DANGER, self._FILL_DANGER
        if level == DangerLevel.WARNING:
            return self._COLOR_WARNING, self._FILL_WARNING
        return self._COLOR_SAFE, self._FILL_SAFE

    def process(self, classification: dai.Buffer) -> None:
        assert isinstance(classification, DangerClassification)

        helper = AnnotationHelper()
        displayed_sources = self._get_displayed_sources(classification)

        state_style = self._STATE_STYLE.get(classification.level)
        if state_style is not None:
            outline_color, state_fill_color = state_style
            helper.draw_rectangle(
                (0.0, 0.0),
                (1.0, 1.0),
                outline_color=outline_color,
                fill_color=state_fill_color,
                thickness=self._STATE_BORDER_THICKNESS,
            )
            state_label = self._STATE_LABEL[classification.level]
            if displayed_sources:
                source_label = " + ".join(
                    self._SOURCE_LABEL[source]
                    for source in displayed_sources
                    if source in self._SOURCE_LABEL
                )
                if source_label:
                    state_label = f"{state_label} ({source_label})"
            helper.draw_text(
                state_label,
                position=self._STATE_LABEL_POSITION,
                color=outline_color,
                size=self._STATE_LABEL_SIZE,
            )

        for danger_detection in classification.danger_detections:
            color, fill_color = self._get_detection_style(danger_detection)
            x_min, y_min, x_max, y_max = danger_detection.bbox

            helper.draw_rectangle(
                (x_min, y_min),
                (x_max, y_max),
                outline_color=color,
                fill_color=fill_color,
                thickness=self._BOX_THICKNESS,
                clip_to_viewport=True,
            )

            label = f"ID:{danger_detection.track_id}"
            point = danger_detection.closest_point_mm
            if point is not None and math.isfinite(point[2]) and point[2] > 0:
                label += f" {point[2] / 1000:.2f}m"

            helper.draw_text(
                label,
                position=(x_min, y_max),
                color=color,
                size=24,
            )

        annotations = helper.build(
            classification.getTimestamp(), classification.getSequenceNum()
        )
        self.out.send(annotations)
