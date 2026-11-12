"""Measures box detections against the active support plane."""

from collections import deque
from statistics import median
from threading import Lock

import cv2
import depthai as dai
import numpy as np
from depthai_nodes.node import BaseHostNode

from solutions_sdk.box_measurement.helper.box_corners import rect_corners
from solutions_sdk.box_measurement.helper.box_geometry import BoxMeasurement
from solutions_sdk.box_measurement.message import (
    BoxDetections,
    BoxDimensions,
    BoxMeasurementResult,
    BoxMeasurements,
    MeasurementStatus,
    SupportPlane,
)

# Fraction of the frame; larger detections are false positives on the whole scene.
MAX_BBOX_AREA = 0.5
# Fraction of the frame; boxes this close to an edge may be cut off.
BORDER_MARGIN = 0.05
# Minimum fraction of mask pixels with a valid point for a box to be measured.
MIN_VALID_POINT_RATIO = 0.90
# Valid measurements per track that the aggregated dimensions are taken over.
MAX_SAMPLES_PER_TRACK = 600
# Consecutive absent frames after which a track's samples are discarded.
MAX_ABSENT_FRAMES = 30


class BoxDimensioner(BaseHostNode):
    """Measure box detections in an organized millimeter point cloud.

    Emits one measurement observation per box detection, with aggregated
    dimensions, on ``out`` and the valid points under all masks on
    ``box_cloud_out``. Both carry the point cloud's timestamps and sequence
    number. The detections' source frame and the cloud must cover the same
    field of view; their resolutions may differ.
    """

    def __init__(self) -> None:
        super().__init__()
        self.box_cloud_out: dai.Node.Output = self.createOutput(name="box_cloud")
        self._plane_lock = Lock()
        self._plane: SupportPlane | None = None
        self._plane_revision = 0
        self._seen_plane_revision = -1
        self._samples: dict[int, deque[BoxDimensions]] = {}
        self._absent: dict[int, int] = {}
        self._geometry = BoxMeasurement()
        self._size: tuple[int, int] | None = None

    def build(
        self,
        detections: dai.Node.Output,
        point_cloud: dai.Node.Output,
        point_cloud_size: tuple[int, int],
        support_plane: SupportPlane | None = None,
    ) -> "BoxDimensioner":
        """Measure ``detections`` in a cloud of ``point_cloud_size`` (w, h)."""
        if self._size is not None:
            raise RuntimeError("BoxDimensioner is already built")
        if len(point_cloud_size) != 2:
            raise ValueError("Point cloud size must be (width, height)")
        if any(
            isinstance(n, bool) or not isinstance(n, int) for n in point_cloud_size
        ):
            raise TypeError("Point cloud dimensions must be integers")
        if any(n <= 0 for n in point_cloud_size):
            raise ValueError("Point cloud dimensions must be positive")
        self._size = (point_cloud_size[0], point_cloud_size[1])
        self.link_args(detections, point_cloud)
        if support_plane is not None:
            self.setSupportPlane(support_plane)
        return self

    def setSupportPlane(self, plane: SupportPlane) -> None:
        """Measure against ``plane`` from the next frame; resets aggregates."""
        if not isinstance(plane, SupportPlane):
            raise TypeError("Expected SupportPlane")
        with self._plane_lock:
            self._plane = plane
            self._plane_revision += 1

    def getSupportPlane(self) -> SupportPlane | None:
        with self._plane_lock:
            return self._plane

    def clearSupportPlane(self) -> None:
        """Stop measuring from the next frame; resets aggregates."""
        with self._plane_lock:
            self._plane = None
            self._plane_revision += 1

    def process(self, detections, point_cloud) -> None:  # pyright: ignore[reportIncompatibleMethodOverride]
        try:
            self._process(detections, point_cloud)
        # DepthAI's stub declares QueueException through an undeclared nested
        # class, so pyright cannot tell it is an exception; at runtime it is one.
        except dai.MessageQueue.QueueException:  # pyright: ignore[reportGeneralTypeIssues]
            return

    def _process(self, detections, point_cloud) -> None:
        if not isinstance(detections, BoxDetections) or not isinstance(
            point_cloud, dai.PointCloudData
        ):
            raise TypeError("Expected box detection and point-cloud messages")
        with self._plane_lock:
            plane, revision = self._plane, self._plane_revision
        if revision != self._seen_plane_revision:
            self._samples.clear()
            self._absent.clear()
            self._seen_plane_revision = revision
        assert self._size is not None
        width, height = self._size
        points = np.asarray(point_cloud.getPoints())
        organized = points.shape == (width * height, 3)
        if organized:
            points = points.reshape(height, width, 3)
        present: set[int] = set()
        results: list[BoxMeasurementResult] = []
        clouds: list[np.ndarray] = []
        for index, detection in enumerate(detections.items):
            track_id = detection.track_id
            present.add(track_id)
            self._absent[track_id] = 0
            rect = detection.bounding_box
            if rect.size.width * rect.size.height > MAX_BBOX_AREA:
                # Omitted, but still present, so its samples are kept.
                continue
            # The mask covers the whole source frame, as the cloud does, so
            # nearest-neighbor resizing maps it onto the cloud grid.
            mask = cv2.resize(
                detections.getMask(index).astype(np.uint8),
                (width, height),
                interpolation=cv2.INTER_NEAREST,
            ).astype(bool)
            xmin, ymin, xmax, ymax = rect_corners(rect)
            border = (
                xmin <= BORDER_MARGIN
                or ymin <= BORDER_MARGIN
                or xmax >= 1 - BORDER_MARGIN
                or ymax >= 1 - BORDER_MARGIN
            )
            status = (
                MeasurementStatus.INELIGIBLE
                if plane is None or border
                else MeasurementStatus.FAILED
            )
            box_points = points[mask] if organized else np.empty((0, 3))
            valid = np.isfinite(box_points).all(axis=1) & (box_points[:, 2] > 1e-6)
            box_points = box_points[valid]
            if box_points.size:
                clouds.append(box_points)
            mask_pixels = int(mask.sum())
            if (
                status == MeasurementStatus.FAILED
                and mask_pixels > 0
                and len(box_points) / mask_pixels >= MIN_VALID_POINT_RATIO
            ):
                assert plane is not None
                try:
                    dimensions = self._geometry.measure(
                        box_points, np.array((*plane.normal, plane.offset_mm))
                    )
                except (ValueError, RuntimeError, cv2.error):
                    dimensions = None
                if dimensions is not None and all(
                    np.isfinite(v) and v > 0
                    for v in (
                        dimensions.length_mm,
                        dimensions.width_mm,
                        dimensions.height_mm,
                    )
                ):
                    self._samples.setdefault(
                        track_id, deque(maxlen=MAX_SAMPLES_PER_TRACK)
                    ).append(dimensions)
                    status = MeasurementStatus.MEASURED
            dimensions = self._aggregate(track_id)
            results.append(
                BoxMeasurementResult(
                    track_id=track_id,
                    bounding_box=rect,
                    confidence=detection.confidence,
                    track_status=detection.track_status,
                    measurement_status=status,
                    dimensions=dimensions,
                )
            )
        for track_id in list(self._absent):
            if track_id in present:
                continue
            self._absent[track_id] += 1
            if self._absent[track_id] >= MAX_ABSENT_FRAMES:
                self._absent.pop(track_id)
                self._samples.pop(track_id, None)
        out = BoxMeasurements(
            results,
            point_cloud.getTimestamp(),
            point_cloud.getTimestampDevice(),
            point_cloud.getSequenceNum(),
        )
        self.out.send(out)
        cloud = dai.PointCloudData()
        output_points = (np.concatenate(clouds) if clouds else np.empty((0, 3))).astype(
            np.float32
        )
        cloud.setPoints(output_points)  # type: ignore[arg-type]
        cloud.setTimestamp(point_cloud.getTimestamp())
        cloud.setTimestampDevice(point_cloud.getTimestampDevice())
        cloud.setSequenceNum(point_cloud.getSequenceNum())
        self.box_cloud_out.send(cloud)

    def _aggregate(self, track_id: int) -> BoxDimensions | None:
        samples = self._samples.get(track_id)
        if not samples:
            return None
        return BoxDimensions(
            length_mm=median(s.length_mm for s in samples),
            width_mm=median(s.width_mm for s in samples),
            height_mm=median(s.height_mm for s in samples),
        )
