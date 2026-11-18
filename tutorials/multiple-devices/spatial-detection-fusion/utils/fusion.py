import collections
from dataclasses import dataclass
from typing import Dict, List

import depthai as dai
import numpy as np
from scipy.optimize import linear_sum_assignment


@dataclass
class FusedDetection:
    """One camera's detection expressed in the reference camera's coordinate system."""

    label: str
    confidence: float
    position: np.ndarray  # [x, y, z] in meters
    camera_index: int


class DetectionGroupBuffer(dai.Buffer):
    """Fused detection groups plus the pose of every camera in the reference frame."""

    def __init__(
        self, groups: List[List[FusedDetection]], camera_poses: List[np.ndarray]
    ):
        super().__init__()
        self.groups = groups
        self.camera_poses = camera_poses


class FusionManager(dai.node.HostNode):
    """Groups the detections that several calibrated devices report for the same object.

    The input is a MessageGroup from a Sync node with one SpatialImgDetections per device.
    The first device's camera is the reference coordinate system.
    """

    def __init__(self) -> None:
        super().__init__()
        self.device_ids: List[str] = []
        self.distance_threshold_m = 0.5
        self.output = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.Buffer, True)
            ]
        )

    def build(
        self,
        synced_detections: dai.Node.Output,
        device_ids: List[str],
        distance_threshold: float,
    ) -> "FusionManager":
        self.device_ids = device_ids
        self.distance_threshold_m = distance_threshold
        self.link_args(synced_detections)
        return self

    def process(self, synced_detections: dai.MessageGroup) -> None:
        # The pipeline calibration makes every transformation point at one common origin,
        # so detections can be moved between cameras of different devices.
        reference = synced_detections[self.device_ids[0]].getTransformation()

        detections: List[FusedDetection] = []
        camera_poses: List[np.ndarray] = []
        for camera_index, device_id in enumerate(self.device_ids):
            message = synced_detections[device_id]
            assert isinstance(message, dai.SpatialImgDetections)
            in_reference = message.transformTo(reference)
            for det in in_reference.detections:
                coords = det.spatialCoordinates
                # filter out ghost detections with z=0
                if coords.z == 0:
                    continue
                detections.append(
                    FusedDetection(
                        label=det.labelName,
                        confidence=det.confidence,
                        position=np.array([coords.x, coords.y, coords.z]) / 1000.0,
                        camera_index=camera_index,
                    )
                )
            camera_poses.append(
                np.array(
                    message.getTransformation()
                    .getExtrinsics()
                    .getExtrinsicsTransformationTo(
                        reference.getExtrinsics(), unit=dai.LengthUnit.METER
                    )
                )
            )

        groups = self._prune_redundant_detections(self._group_detections(detections))

        buffer = DetectionGroupBuffer(groups, camera_poses)
        buffer.setTimestamp(synced_detections.getTimestamp())
        buffer.setSequenceNum(synced_detections.getSequenceNum())
        self.output.send(buffer)

    def _prune_redundant_detections(
        self, groups: List[List[FusedDetection]]
    ) -> List[List[FusedDetection]]:
        """
        For each group, ensure that each camera is represented by at most one detection
        (the one with the highest confidence).
        """
        pruned_groups = []
        for group in groups:
            best_det_per_cam: Dict[int, FusedDetection] = {}

            for det in group:
                cam_id = det.camera_index
                if (
                    cam_id not in best_det_per_cam
                    or det.confidence > best_det_per_cam[cam_id].confidence
                ):
                    best_det_per_cam[cam_id] = det

            pruned_groups.append(list(best_det_per_cam.values()))

        return pruned_groups

    def _group_detections(
        self, detections: List[FusedDetection]
    ) -> List[List[FusedDetection]]:
        """
        Groups detections using the Hungarian algorithm for optimal assignment,
        then finds connected components to form final groups.
        """
        if not detections:
            return []

        detections_by_label = collections.defaultdict(list)
        for det in detections:
            detections_by_label[det.label].append(det)

        all_groups = []

        for _, dets in detections_by_label.items():
            num_dets = len(dets)
            if num_dets <= 1:
                all_groups.append(dets)
                continue

            cost_matrix = np.full((num_dets, num_dets), np.inf)
            for i in range(num_dets):
                for j in range(i + 1, num_dets):
                    dist = np.linalg.norm(dets[i].position - dets[j].position)
                    cost_matrix[i, j] = dist
                    cost_matrix[j, i] = dist

            row_ind, col_ind = linear_sum_assignment(cost_matrix)

            adj = collections.defaultdict(list)
            for r, c in zip(row_ind, col_ind):
                if r < c and cost_matrix[r, c] < self.distance_threshold_m:
                    adj[r].append(c)
                    adj[c].append(r)

            visited = set()
            for i in range(num_dets):
                if i not in visited:
                    current_group_indices = []
                    q = collections.deque([i])
                    visited.add(i)
                    while q:
                        u = q.popleft()
                        current_group_indices.append(u)
                        for v in adj.get(u, []):
                            if v not in visited:
                                visited.add(v)
                                q.append(v)

                    all_groups.append([dets[idx] for idx in current_group_indices])

        return all_groups
