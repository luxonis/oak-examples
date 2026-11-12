"""Per-frame box detections, before any measurement."""

from datetime import timedelta
from typing import ClassVar

import depthai as dai
import numpy as np
from depthai_nodes.message import Collection
from pydantic import BaseModel, ConfigDict

from solutions_sdk.box_measurement.helper.box_annotations import build_box_annotations

BACKGROUND_LABEL = 255


class BoxDetection(BaseModel):
    """A tracked box's identity and location in one processed frame.

    Its segmentation is the region of the owning ``BoxDetections`` mask labelled
    with this item's index.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(
        arbitrary_types_allowed=True, frozen=True
    )

    track_id: int
    bounding_box: dai.RotatedRect
    confidence: float
    track_status: dai.Tracklet.TrackingStatus


class BoxDetections(Collection[BoxDetection]):
    """Box detections sharing one segmentation label mask.

    The mask covers the whole source frame, stretched to its own resolution. A
    pixel value is the index of the item it belongs to; 255 is background.
    """

    def __init__(
        self,
        items: list[BoxDetection],
        segmentation_mask: np.ndarray,
        timestamp: timedelta,
        timestamp_device: timedelta,
        sequence_num: int,
    ):
        super().__init__(items)
        if not isinstance(segmentation_mask, np.ndarray):
            raise TypeError("Segmentation mask must be a numpy array")
        if segmentation_mask.ndim != 2 or segmentation_mask.dtype != np.uint8:
            raise ValueError("Segmentation mask must be a 2-D uint8 label image")
        labels = segmentation_mask[segmentation_mask != BACKGROUND_LABEL]
        if labels.size and int(labels.max()) >= len(items):
            raise ValueError("Segmentation mask labels must index detection items")
        self._segmentation_mask = segmentation_mask
        self.setTimestamp(timestamp)
        self.setTimestampDevice(timestamp_device)
        self.setSequenceNum(sequence_num)

    @property
    def segmentation_mask(self) -> np.ndarray:
        """The shared ``uint8`` label mask; 255 marks background."""
        return self._segmentation_mask

    def getMask(self, index: int) -> np.ndarray:
        """Return the boolean segmentation mask of the item at ``index``."""
        if not 0 <= index < len(self.items):
            raise IndexError("Detection index out of range")
        return self._segmentation_mask == index

    def getVisualizationMessage(self) -> dai.ImgAnnotations:
        """Outline each box, labelled with its track ID and confidence."""
        return build_box_annotations(
            [
                (box.bounding_box, f"Box {box.track_id} ({box.confidence:.0%})")
                for box in self.items
            ],
            self.getTimestamp(),
            self.getTimestampDevice(),
            self.getSequenceNum(),
        )
