"""Pairs tracklets with segmented detections into one BoxDetections per frame."""

import depthai as dai
import numpy as np

from solutions_sdk.box_measurement.helper.box_corners import rect_from_corners
from solutions_sdk.box_measurement.helper.segmentation_matching import (
    SegmentationMatcher,
)
from solutions_sdk.box_measurement.message import (
    BACKGROUND_LABEL,
    BoxDetection,
    BoxDetections,
)


class BoxDetectionAssembler(dai.node.HostNode):
    """Emit one box detection per tracked box with a non-empty segmentation."""

    def __init__(self) -> None:
        super().__init__()
        self._matcher = SegmentationMatcher()
        self._mask_size = (1, 1)

    def build(
        self,
        tracklets: dai.Node.Output,
        detections: dai.Node.Output,
        mask_size: tuple[int, int],
    ) -> "BoxDetectionAssembler":
        """Pair tracker and NN outputs; ``mask_size`` is the NN input (w, h)."""
        self._mask_size = mask_size
        self.link_args(tracklets, detections)
        return self

    def process(self, tracklets, detections) -> None:
        try:
            self.out.send(self._assemble(tracklets, detections))
        # DepthAI's stub declares QueueException through an undeclared nested
        # class, so pyright cannot tell it is an exception; at runtime it is one.
        except dai.MessageQueue.QueueException:  # pyright: ignore[reportGeneralTypeIssues]
            return

    def _assemble(self, tracklets, detections) -> BoxDetections:
        if not isinstance(tracklets, dai.Tracklets) or not isinstance(
            detections, dai.ImgDetections
        ):
            raise TypeError("Expected internal tracking and detection messages")
        source_mask = detections.getCvSegmentationMask()
        items: list[BoxDetection] = []
        if source_mask is None or source_mask.ndim != 2:
            width, height = self._mask_size
            mask = np.full((height, width), BACKGROUND_LABEL, dtype=np.uint8)
        else:
            mask = np.full(source_mask.shape, BACKGROUND_LABEL, dtype=np.uint8)
            active = [
                t
                for t in tracklets.tracklets
                if t.status != dai.Tracklet.TrackingStatus.REMOVED
            ]
            matches = self._matcher.match(active, detections.detections)
            for track_index, det_index in matches.items():
                region = source_mask == det_index
                if not region.any() or len(items) >= BACKGROUND_LABEL:
                    continue
                mask[region] = len(items)
                track, det = active[track_index], detections.detections[det_index]
                # NN uses stretch resizing, so normalized boxes already use the
                # source frame's coordinates.
                rect = rect_from_corners(det.xmin, det.ymin, det.xmax, det.ymax)
                items.append(
                    BoxDetection(
                        track_id=int(track.id),
                        bounding_box=rect,
                        confidence=det.confidence,
                        track_status=track.status,
                    )
                )
        return BoxDetections(
            items,
            mask,
            detections.getTimestamp(),
            detections.getTimestampDevice(),
            detections.getSequenceNum(),
        )
