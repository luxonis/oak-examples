import logging
from typing import Sequence

import depthai as dai
import numpy as np

from depthai_pipeline.nn_person_detection.message.tracked_segmentation import (
    SegmentationMask,
    TrackedSegmentation,
    TrackedSegmentationFrame,
)

logger = logging.getLogger(__name__)


class TrackletSegmentationMatcher(dai.node.HostNode):
    """Attach instance masks to native tracklets using same-frame box overlap.

    DepthAI's tracker assigns IDs, while the segmentation payload indexes detections.
    This node associates those two outputs and keeps the last mask for active tracks.
    """

    _DEFAULT_STALE_CACHE_FRAMES = 120

    def build(
        self,
        tracklets: dai.Node.Output,
        detections: dai.Node.Output,
        stale_cache_frames: int = _DEFAULT_STALE_CACHE_FRAMES,
    ) -> "TrackletSegmentationMatcher":
        """Link tracker and detection outputs and initialize the mask cache.

        Args:
            tracklets: Native ObjectTracker output.
            detections: Detections with an indexed segmentation mask payload.
            stale_cache_frames: Frames to retain a mask after its track disappears.

        Returns:
            This configured node.
        """
        self.link_args(tracklets, detections)
        self._stale_cache_frames = stale_cache_frames
        self._segmentation_cache: dict[int, SegmentationMask] = {}
        self._unseen_frame_counts: dict[int, int] = {}
        return self

    def process(self, tracklets_msg: dai.Buffer, detections_msg: dai.Buffer) -> None:
        try:
            assert isinstance(tracklets_msg, dai.Tracklets)
            assert isinstance(detections_msg, dai.ImgDetections)

            active_tracklets: list[dai.Tracklet] = []
            active_track_ids: set[int] = set()
            removed_track_ids: set[int] = set()
            for tracklet in tracklets_msg.tracklets:
                track_id = int(tracklet.id)
                if tracklet.status == dai.Tracklet.TrackingStatus.REMOVED:
                    removed_track_ids.add(track_id)
                    continue
                active_tracklets.append(tracklet)
                active_track_ids.add(track_id)

            self._drop_removed_cache_entries(removed_track_ids)

            detections = list(detections_msg.detections)
            detection_masks = self._extract_detection_masks(detections_msg, detections)
            matches = self._match_tracklets(active_tracklets, detections)

            enriched_tracks: list[TrackedSegmentation] = []
            unmatched_track_ids: list[int] = []
            for track_index, tracklet in enumerate(active_tracklets):
                track_id = int(tracklet.id)
                segmentation_mask: SegmentationMask | None = None
                matched_detection_index = matches.get(track_index)

                if matched_detection_index is not None:
                    segmentation_mask = detection_masks.get(matched_detection_index)
                    if segmentation_mask is not None:
                        self._segmentation_cache[track_id] = segmentation_mask
                    else:
                        logger.debug(
                            "Tracklet %s matched detection %s, but no segmentation mask "
                            "pixels were available; trying cached payload",
                            track_id,
                            matched_detection_index,
                        )

                if segmentation_mask is None:
                    # A tracked person can remain active without a fresh detection.
                    segmentation_mask = self._segmentation_cache.get(track_id)
                    if matched_detection_index is None and segmentation_mask is None:
                        unmatched_track_ids.append(track_id)

                self._unseen_frame_counts[track_id] = 0
                enriched_tracks.append(
                    TrackedSegmentation(
                        tracklet=tracklet,
                        segmentation_mask=segmentation_mask,
                    )
                )

            if unmatched_track_ids:
                logger.debug(
                    "Tracklets without a same-frame detection match or cached segmentation "
                    "payload: %s",
                    unmatched_track_ids,
                )

            self._evict_stale_cache_entries(active_track_ids)

            tracked_segmentation_frame = TrackedSegmentationFrame()
            tracked_segmentation_frame.tracks = enriched_tracks
            tracked_segmentation_frame.setSequenceNum(tracklets_msg.getSequenceNum())
            tracked_segmentation_frame.setTimestamp(tracklets_msg.getTimestamp())
            tracked_segmentation_frame.setTimestampDevice(
                tracklets_msg.getTimestampDevice()
            )
            self.out.send(tracked_segmentation_frame)
        except dai.MessageQueue.QueueException:
            return

    @staticmethod
    def _tracklet_bbox(tracklet: dai.Tracklet) -> tuple[float, float, float, float]:
        roi = tracklet.roi
        top_left = roi.topLeft()
        bottom_right = roi.bottomRight()
        return top_left.x, top_left.y, bottom_right.x, bottom_right.y

    @staticmethod
    def _detection_bbox(
        detection: dai.ImgDetection,
    ) -> tuple[float, float, float, float]:
        return detection.xmin, detection.ymin, detection.xmax, detection.ymax

    @staticmethod
    def _bbox_iou(
        left: tuple[float, float, float, float],
        right: tuple[float, float, float, float],
    ) -> float:
        left_xmin, left_ymin, left_xmax, left_ymax = left
        right_xmin, right_ymin, right_xmax, right_ymax = right

        intersection_xmin = max(left_xmin, right_xmin)
        intersection_ymin = max(left_ymin, right_ymin)
        intersection_xmax = min(left_xmax, right_xmax)
        intersection_ymax = min(left_ymax, right_ymax)

        intersection_width = max(0.0, intersection_xmax - intersection_xmin)
        intersection_height = max(0.0, intersection_ymax - intersection_ymin)
        intersection_area = intersection_width * intersection_height
        if intersection_area <= 0.0:
            return 0.0

        left_area = max(0.0, left_xmax - left_xmin) * max(0.0, left_ymax - left_ymin)
        right_area = max(0.0, right_xmax - right_xmin) * max(
            0.0, right_ymax - right_ymin
        )
        union_area = left_area + right_area - intersection_area
        if union_area <= 0.0:
            return 0.0

        return intersection_area / union_area

    def _match_tracklets(
        self,
        tracklets: list[dai.Tracklet],
        detections: Sequence[dai.ImgDetection],
    ) -> dict[int, int]:
        """Greedily assign unique detections to tracks by descending box IoU.

        Returns:
            Mapping from tracklet list index to detection list index.
        """
        candidate_matches: list[tuple[float, int, int]] = []
        for track_index, tracklet in enumerate(tracklets):
            tracklet_bbox = self._tracklet_bbox(tracklet)
            for detection_index, detection in enumerate(detections):
                iou = self._bbox_iou(tracklet_bbox, self._detection_bbox(detection))
                if iou > 0.0:
                    candidate_matches.append((iou, track_index, detection_index))

        candidate_matches.sort(reverse=True)

        assigned_track_indexes: set[int] = set()
        assigned_detection_indexes: set[int] = set()
        matches: dict[int, int] = {}
        for _iou, track_index, detection_index in candidate_matches:
            if track_index in assigned_track_indexes:
                continue
            if detection_index in assigned_detection_indexes:
                continue

            assigned_track_indexes.add(track_index)
            assigned_detection_indexes.add(detection_index)
            matches[track_index] = detection_index

        return matches

    def _extract_detection_masks(
        self,
        detections_msg: dai.ImgDetections,
        detections: Sequence[dai.ImgDetection],
    ) -> dict[int, SegmentationMask]:
        """Split the indexed payload into one boolean mask per detection.

        The payload's pixel value is the detection index; pixels with other
        values, including the background value, are excluded.
        """
        if not detections:
            return {}

        mask_array = detections_msg.getCvSegmentationMask()
        if mask_array is None or mask_array.size == 0:
            logger.warning(
                "Received %s detections but no segmentation mask payload was attached",
                len(detections),
            )
            return {}

        detection_masks: dict[int, SegmentationMask] = {}
        for detection_index in range(len(detections)):
            detection_mask = np.equal(mask_array, detection_index)
            if detection_mask.any():
                detection_masks[detection_index] = detection_mask.copy()

        if len(detection_masks) < len(detections):
            logger.debug(
                "Only %s of %s detections had pixels in the segmentation mask payload",
                len(detection_masks),
                len(detections),
            )

        return detection_masks

    def _drop_removed_cache_entries(self, removed_track_ids: set[int]) -> None:
        dropped_track_ids = [
            track_id
            for track_id in removed_track_ids
            if track_id in self._segmentation_cache
        ]
        for track_id in removed_track_ids:
            self._segmentation_cache.pop(track_id, None)
            self._unseen_frame_counts.pop(track_id, None)

        if dropped_track_ids:
            logger.debug(
                "Cleared cached segmentation payloads for removed tracklets: %s",
                dropped_track_ids,
            )

    def _evict_stale_cache_entries(self, active_track_ids: set[int]) -> None:
        """Evict masks for tracks absent from the output for enough frames."""
        stale_track_ids: list[int] = []
        for track_id in list(self._segmentation_cache):
            if track_id in active_track_ids:
                continue

            unseen_frames = self._unseen_frame_counts.get(track_id, 0) + 1
            self._unseen_frame_counts[track_id] = unseen_frames
            if unseen_frames >= self._stale_cache_frames:
                stale_track_ids.append(track_id)

        for track_id in stale_track_ids:
            self._segmentation_cache.pop(track_id, None)
            self._unseen_frame_counts.pop(track_id, None)

        if stale_track_ids:
            logger.debug(
                "Evicted stale cached segmentation payloads for tracklets: %s",
                stale_track_ids,
            )
