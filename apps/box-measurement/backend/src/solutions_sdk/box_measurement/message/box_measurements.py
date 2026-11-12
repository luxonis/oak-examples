"""Public per-frame observations; completion and recording remain caller policy."""

from datetime import timedelta
from enum import Enum
from typing import ClassVar

import depthai as dai
from depthai_nodes.message import Collection
from pydantic import BaseModel, ConfigDict, model_validator

from solutions_sdk.box_measurement.helper.box_annotations import build_box_annotations


class BoxDimensions(BaseModel):
    """A box's length, width, and height in millimeters."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    length_mm: float
    width_mm: float
    height_mm: float

    @property
    def volume_mm3(self) -> float:
        return self.length_mm * self.width_mm * self.height_mm


class MeasurementStatus(str, Enum):
    INELIGIBLE = "ineligible"
    FAILED = "failed"
    MEASURED = "measured"


class BoxMeasurementResult(BaseModel):
    """A tracked box's measurement outcome in one processed frame.

    ``dimensions`` are the box's aggregated dimensions, when it has any.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(
        arbitrary_types_allowed=True, frozen=True
    )

    track_id: int
    bounding_box: dai.RotatedRect
    confidence: float
    track_status: dai.Tracklet.TrackingStatus
    measurement_status: MeasurementStatus
    dimensions: BoxDimensions | None = None

    @model_validator(mode="after")
    def _measured_has_dimensions(self) -> "BoxMeasurementResult":
        if (
            self.measurement_status == MeasurementStatus.MEASURED
            and self.dimensions is None
        ):
            raise ValueError("A measured observation requires dimensions")
        return self


class BoxMeasurements(Collection[BoxMeasurementResult]):
    def __init__(
        self,
        items: list[BoxMeasurementResult],
        timestamp: timedelta,
        timestamp_device: timedelta,
        sequence_num: int,
    ):
        super().__init__(items)
        self.setTimestamp(timestamp)
        self.setTimestampDevice(timestamp_device)
        self.setSequenceNum(sequence_num)

    def getVisualizationMessage(self) -> dai.ImgAnnotations:
        """Render tracked boxes and available aggregated dimensions."""
        return build_box_annotations(
            [(box.bounding_box, _label(box)) for box in self.items],
            self.getTimestamp(),
            self.getTimestampDevice(),
            self.getSequenceNum(),
        )


def _label(box: BoxMeasurementResult) -> str:
    label = f"Box {box.track_id} ({box.confidence:.0%})"
    dimensions = box.dimensions
    if dimensions is not None:
        label += (
            f"\nH: {dimensions.height_mm / 10:.1f} cm"
            f"\nL: {dimensions.length_mm / 10:.1f} cm"
            f" W: {dimensions.width_mm / 10:.1f} cm"
            f"\nV: {dimensions.volume_mm3 / 1000:.0f} cm³"
        )
    return label
