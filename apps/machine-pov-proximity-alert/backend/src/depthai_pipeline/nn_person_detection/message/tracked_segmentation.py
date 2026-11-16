from dataclasses import dataclass

import depthai as dai
import numpy as np
import numpy.typing as npt

SegmentationMask = npt.NDArray[np.bool_]


@dataclass(slots=True)
class TrackedSegmentation:
    """Native tracklet paired with an aligned boolean mask, if available."""

    tracklet: dai.Tracklet
    segmentation_mask: SegmentationMask | None


class TrackedSegmentationFrame(dai.Buffer):
    """All tracked segmentations for one synchronized frame."""

    def __init__(self):
        super().__init__()
        self._tracks: list[TrackedSegmentation] = []

    @property
    def tracks(self) -> list[TrackedSegmentation]:
        return self._tracks

    @tracks.setter
    def tracks(self, value: list[TrackedSegmentation]):
        self._tracks = value
