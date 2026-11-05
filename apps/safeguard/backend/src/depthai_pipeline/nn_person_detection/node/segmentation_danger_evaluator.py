import logging
import math
from typing import cast

import cv2
import depthai as dai
import numpy as np

from depthai_pipeline.common.message.danger_assessment import DangerAssessment
from depthai_pipeline.common.message.danger_classification import (
    DangerLevel,
    DangerSource,
    DangerSpatialDetection,
)
from depthai_pipeline.nn_person_detection.message.tracked_segmentation import (
    TrackedSegmentation,
    TrackedSegmentationFrame,
)
from settings.settings import SpatialZone
from util.ground_alignment import rotation_from_imu

logger = logging.getLogger(__name__)


class SegmentationDangerEvaluator(dai.node.HostNode):
    """Classify tracked person masks against ground-aligned spatial zones.

    Depth pixels are back-projected to millimeters and rotated using IMU
    orientation before their horizontal position is checked against each zone.
    """

    _DEFAULT_THRESHOLD_LOW = 200
    _DEFAULT_THRESHOLD_HIGH = 30000
    _DEFAULT_DEPTH_SOCKET = dai.CameraBoardSocket.CAM_A
    _DEFAULT_DISTANCE_INSIDE = 7
    _REBUILD_R_INTERVAL = 10

    def __init__(self) -> None:
        super().__init__()
        self._danger_roi: SpatialZone | None = None
        self._warning_roi: SpatialZone | None = None
        self._thresh_low = self._DEFAULT_THRESHOLD_LOW
        self._thresh_high = self._DEFAULT_THRESHOLD_HIGH
        self._depth_socket = self._DEFAULT_DEPTH_SOCKET
        diameter = 2 * self._DEFAULT_DISTANCE_INSIDE + 1
        self._erode_kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (diameter, diameter)
        )
        self._intrinsics_inv: np.ndarray | None = None

        self._imu_input = self.createInput()
        self._latest_imu: dai.IMUData | None = None

        self._R: np.ndarray | None = None
        self._frames_since_R = self._REBUILD_R_INTERVAL

    def build(
        self,
        tracked_segmentations: dai.Node.Output,
        depth: dai.Node.Output,
        imu: dai.Node.Output,
        danger_roi: SpatialZone | None = None,
        warning_roi: SpatialZone | None = None,
        thresh_low: int = _DEFAULT_THRESHOLD_LOW,
        thresh_high: int = _DEFAULT_THRESHOLD_HIGH,
        depth_socket: dai.CameraBoardSocket = _DEFAULT_DEPTH_SOCKET,
        distance_inside: int = _DEFAULT_DISTANCE_INSIDE,
    ) -> "SegmentationDangerEvaluator":
        """Configure the depth and zone inputs for spatial evaluation.

        Args:
            tracked_segmentations: Tracklets paired with their instance masks.
            depth: Depth image aligned to the segmentation masks.
            imu: IMU samples used to align points with the ground.
            danger_roi: Inner zone, checked before the warning zone.
            warning_roi: Outer zone.
            thresh_low: Minimum accepted depth in millimeters.
            thresh_high: Maximum accepted depth in millimeters.
            depth_socket: Camera whose calibration applies to the depth image.
            distance_inside: Mask erosion radius in pixels.

        Returns:
            This configured node.
        """
        imu.link(self._imu_input)
        self.link_args(tracked_segmentations, depth)
        self._danger_roi = danger_roi
        self._warning_roi = warning_roi
        self._thresh_low = thresh_low
        self._thresh_high = thresh_high
        self._depth_socket = depth_socket
        diameter = 2 * distance_inside + 1
        self._erode_kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (diameter, diameter)
        )
        self._intrinsics_inv = None
        return self

    def process(
        self,
        tracked_segmentations: dai.Buffer,
        depth: dai.ImgFrame,
    ) -> None:
        try:
            assert isinstance(tracked_segmentations, TrackedSegmentationFrame)
            while True:
                new_imu = self._imu_input.tryGet()
                if new_imu is None:
                    break
                self._latest_imu = cast(dai.IMUData, new_imu)
            self._rebuild_R_if_needed()
            if self._R is None:
                # Ground orientation unavailable: cannot classify points into ground-aligned zones
                assessment = DangerAssessment()
                assessment.source = DangerSource.SEGMENTATION
                assessment.level = DangerLevel.SAFE
                assessment.available = False
                assessment.danger_detections = []
                assessment.nearest_point_mm = None
                assessment.setSequenceNum(tracked_segmentations.getSequenceNum())
                assessment.setTimestamp(tracked_segmentations.getTimestamp())
                assessment.setTimestampDevice(
                    tracked_segmentations.getTimestampDevice()
                )
                self.out.send(assessment)
                return
            raw_level, danger_detections = self._evaluate_tracks(
                tracked_segmentations.tracks,
                depth.getFrame(),
            )
            assessment = DangerAssessment()
            assessment.source = DangerSource.SEGMENTATION
            assessment.level = raw_level
            assessment.available = True
            assessment.danger_detections = danger_detections
            assessment.nearest_point_mm = self._nearest_detection_point(
                danger_detections, raw_level
            )
            assessment.setSequenceNum(tracked_segmentations.getSequenceNum())
            assessment.setTimestamp(tracked_segmentations.getTimestamp())
            assessment.setTimestampDevice(tracked_segmentations.getTimestampDevice())
            self.out.send(assessment)
        except dai.MessageQueue.QueueException:
            return

    def _rebuild_R_if_needed(self) -> None:
        """Rebuild self._R from the latest IMU sample every _REBUILD_R_INTERVAL frames."""
        self._frames_since_R += 1
        if self._R is not None and self._frames_since_R < self._REBUILD_R_INTERVAL:
            return
        if self._latest_imu is None:
            return
        imu_up = self._extract_gravity_vector(self._latest_imu)
        if imu_up is None:
            return
        new_R = rotation_from_imu(imu_up)
        if new_R is not None:
            self._R = new_R
            self._frames_since_R = 0

    @staticmethod
    def _extract_gravity_vector(imu_msg: dai.IMUData) -> np.ndarray | None:
        """Pull the latest accelerometer reading from an IMU message."""
        for pkt in imu_msg.packets:
            if hasattr(pkt, "acceleroMeter") and pkt.acceleroMeter is not None:
                a = pkt.acceleroMeter
                return np.array([a.x, a.y, a.z], dtype=np.float32)
        return None

    def _get_intrinsics_inv(self, depth_w: int, depth_h: int) -> np.ndarray:
        if self._intrinsics_inv is None:
            calib_data = self.getParentPipeline().getDefaultDevice().getCalibration()
            intrinsics = np.array(
                calib_data.getCameraIntrinsics(
                    cameraId=self._depth_socket,
                    resizeWidth=depth_w,
                    resizeHeight=depth_h,
                ),
                dtype=np.float32,
            )
            self._intrinsics_inv = np.linalg.inv(intrinsics)

        return self._intrinsics_inv

    @staticmethod
    def _nearest_detection_point(
        danger_detections: list[DangerSpatialDetection],
        raw_level: DangerLevel,
    ) -> tuple[float, float, float] | None:
        nearest_point_mm: tuple[float, float, float] | None = None

        for detection in danger_detections:
            if detection.danger_zone != raw_level or detection.closest_point_mm is None:
                continue

            if (
                nearest_point_mm is None
                or detection.closest_point_mm[2] < nearest_point_mm[2]
            ):
                nearest_point_mm = detection.closest_point_mm

        return nearest_point_mm

    @staticmethod
    def _empty_danger_detection(tracklet: dai.Tracklet) -> DangerSpatialDetection:
        return DangerSpatialDetection(
            track_id=int(tracklet.id),
            bbox=SegmentationDangerEvaluator._track_bbox(tracklet),
            closest_point_mm=None,
            centroid_point_mm=None,
            danger_zone=DangerLevel.SAFE,
        )

    def _get_danger_detection(
        self,
        tracked_segmentation: TrackedSegmentation,
        depth_frame: np.ndarray,
        intrinsics_inv: np.ndarray,
    ) -> DangerSpatialDetection:
        tracklet = tracked_segmentation.tracklet
        segmentation_mask = tracked_segmentation.segmentation_mask
        if segmentation_mask is None:
            logger.debug(
                "Tracklet %s has no segmentation payload for spatial zone evaluation",
                int(tracklet.id),
            )
            return self._empty_danger_detection(tracklet)

        depth_h, depth_w = depth_frame.shape[:2]
        mask_h, mask_w = segmentation_mask.shape[:2]
        if mask_h != depth_h or mask_w != depth_w:
            logger.warning(
                "Segmentation mask size (%sx%s) does not match aligned depth size "
                "(%sx%s).",
                mask_w,
                mask_h,
                depth_w,
                depth_h,
            )
            return self._empty_danger_detection(tracklet)

        points_mm = self._get_detection_3d_points_mm(
            segmentation_mask=segmentation_mask,
            depth_frame=depth_frame,
            intrinsics_inv=intrinsics_inv,
            tracklet=tracklet,
        )
        if points_mm is None:
            return self._empty_danger_detection(tracklet)

        closest_idx = int(np.argmin(points_mm[:, 2]))
        closest_point = points_mm[closest_idx]
        centroid_point = np.mean(points_mm, axis=0)
        return DangerSpatialDetection(
            track_id=int(tracklet.id),
            bbox=self._track_bbox(tracklet),
            closest_point_mm=(
                float(closest_point[0]),
                float(closest_point[1]),
                float(closest_point[2]),
            ),
            centroid_point_mm=(
                float(centroid_point[0]),
                float(centroid_point[1]),
                float(centroid_point[2]),
            ),
            danger_zone=self._get_danger_zone(
                x_mm=points_mm[:, 0],
                z_mm=points_mm[:, 2],
            ),
        )

    def _get_detection_3d_points_mm(
        self,
        segmentation_mask: np.ndarray,
        depth_frame: np.ndarray,
        intrinsics_inv: np.ndarray,
        tracklet: dai.Tracklet,
    ) -> np.ndarray | None:
        """Back-project valid mask pixels into ground-aligned 3D points.

        The mask is eroded to reduce edge depth bleed. Depths outside the
        configured range or the 2nd–98th percentile are excluded.

        Args:
            segmentation_mask: Boolean person mask aligned to the depth frame.
            depth_frame: Depth image in millimeters.
            intrinsics_inv: Inverse camera intrinsics for this depth resolution.
            tracklet: Track whose box bounds the pixels to examine.

        Returns:
            Nx3 points in millimeters, or None when no valid pixels remain.
        """
        segmentation_mask = segmentation_mask.astype(bool, copy=False)

        depth_h, depth_w = depth_frame.shape[:2]
        pad = self._erode_kernel.shape[0] // 2

        roi_px = self._tracklet_roi_px(
            tracklet=tracklet,
            width=depth_w,
            height=depth_h,
            pad=pad,
        )
        if roi_px is None:
            return None

        x0, y0, x1, y1 = roi_px
        mask_roi = segmentation_mask[y0:y1, x0:x1]
        depth_roi = depth_frame[y0:y1, x0:x1]

        if not mask_roi.any():
            return None

        eroded_mask_u8 = cv2.erode(
            mask_roi.astype(np.uint8, copy=False),
            self._erode_kernel,
            borderType=cv2.BORDER_CONSTANT,
            borderValue=(0,),
        )
        eroded_mask = eroded_mask_u8.astype(bool, copy=False)
        valid = (
            eroded_mask
            & (depth_roi >= self._thresh_low)
            & (depth_roi <= self._thresh_high)
        )
        valid_depths = depth_roi[valid]
        if valid_depths.size == 0:
            return None

        ys, xs = np.where(valid)
        low, high = np.percentile(valid_depths, [2, 98])
        inlier_mask = (valid_depths >= low) & (valid_depths <= high)
        inlier_depths = valid_depths[inlier_mask].astype(np.float32, copy=False)
        if inlier_depths.size == 0:
            return None

        inlier_xs = (xs[inlier_mask] + x0).astype(np.float32, copy=False)
        inlier_ys = (ys[inlier_mask] + y0).astype(np.float32, copy=False)

        # Inline pixel-to-ray back-projection instead of K_inv @ stacked_pixels
        # to avoid extra allocations on the hot path.
        ray_x = (
            intrinsics_inv[0, 0] * inlier_xs
            + intrinsics_inv[0, 1] * inlier_ys
            + intrinsics_inv[0, 2]
        )
        ray_y = (
            intrinsics_inv[1, 0] * inlier_xs
            + intrinsics_inv[1, 1] * inlier_ys
            + intrinsics_inv[1, 2]
        )
        ray_z = (
            intrinsics_inv[2, 0] * inlier_xs
            + intrinsics_inv[2, 1] * inlier_ys
            + intrinsics_inv[2, 2]
        )

        x_mm = ray_x * inlier_depths
        y_mm = ray_y * inlier_depths
        z_mm = ray_z * inlier_depths

        # Rotate points into ground-aligned frame before zone checks
        assert self._R is not None
        R = self._R.astype(np.float32, copy=False)

        x_g = R[0, 0] * x_mm + R[0, 1] * y_mm + R[0, 2] * z_mm
        z_g = R[2, 0] * x_mm + R[2, 1] * y_mm + R[2, 2] * z_mm

        # Height is retained for the centroid; zone membership uses x and z.
        y_g = R[1, 0] * x_mm + R[1, 1] * y_mm + R[1, 2] * z_mm

        points_mm = np.stack([x_g, y_g, z_g], axis=1)
        return points_mm

    def _tracklet_roi_px(
        self,
        tracklet: dai.Tracklet,
        width: int,
        height: int,
        pad: int,
    ) -> tuple[int, int, int, int] | None:
        """Convert a normalized track box to a padded, clipped pixel ROI."""
        roi = tracklet.roi
        top_left = roi.topLeft()
        bottom_right = roi.bottomRight()

        x0 = max(0, min(width, math.floor(top_left.x * width) - pad))
        y0 = max(0, min(height, math.floor(top_left.y * height) - pad))
        x1 = max(0, min(width, math.ceil(bottom_right.x * width) + pad))
        y1 = max(0, min(height, math.ceil(bottom_right.y * height) + pad))

        if x1 <= x0 or y1 <= y0:
            return None

        return x0, y0, x1, y1

    def _is_in_zone(
        self,
        x_mm: np.ndarray | None,
        z_mm: np.ndarray | None,
        zone: SpatialZone | None,
    ) -> bool:
        if x_mm is None or z_mm is None:
            return False
        if zone is None:
            return False

        return bool(
            (
                (z_mm <= zone.distance_mm)
                & (x_mm >= zone.x_min_mm)
                & (x_mm <= zone.x_max_mm)
            ).any()
        )

    def _get_danger_zone(
        self,
        x_mm: np.ndarray | None,
        z_mm: np.ndarray | None,
    ) -> DangerLevel:
        if self._is_in_zone(
            x_mm,
            z_mm,
            self._danger_roi,
        ):
            return DangerLevel.DANGER
        if self._is_in_zone(
            x_mm,
            z_mm,
            self._warning_roi,
        ):
            return DangerLevel.WARNING
        return DangerLevel.SAFE

    @staticmethod
    def _track_bbox(tracklet: dai.Tracklet) -> tuple[float, float, float, float]:
        roi = tracklet.roi
        top_left = roi.topLeft()
        bottom_right = roi.bottomRight()
        return top_left.x, top_left.y, bottom_right.x, bottom_right.y

    def _evaluate_tracks(
        self,
        tracks: list[TrackedSegmentation],
        depth_frame: np.ndarray,
    ) -> tuple[DangerLevel, list[DangerSpatialDetection]]:
        danger_detected = False
        warning_detected = False
        danger_detections: list[DangerSpatialDetection] = []
        intrinsics_inv = self._get_intrinsics_inv(
            depth_frame.shape[1],
            depth_frame.shape[0],
        )

        for tracked_segmentation in tracks:
            tracklet = tracked_segmentation.tracklet
            if tracklet.status == dai.Tracklet.TrackingStatus.REMOVED:
                continue

            danger_detection = self._get_danger_detection(
                tracked_segmentation,
                depth_frame,
                intrinsics_inv,
            )
            danger_detections.append(danger_detection)

            if danger_detection.danger_zone == DangerLevel.DANGER:
                danger_detected = True
            if danger_detection.danger_zone == DangerLevel.WARNING:
                warning_detected = True

        if danger_detected:
            return DangerLevel.DANGER, danger_detections
        if warning_detected:
            return DangerLevel.WARNING, danger_detections
        return DangerLevel.SAFE, danger_detections
