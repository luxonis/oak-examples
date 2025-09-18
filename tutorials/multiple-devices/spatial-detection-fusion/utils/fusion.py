import depthai as dai
import time
import datetime
import collections
import numpy as np
import bisect
from typing import Dict, List, Any
from scipy.optimize import linear_sum_assignment

from .detection_object import WorldDetection


class DetectionGroupBuffer(dai.Buffer):
    """
    A custom buffer class to hold fused detection groups directly.
    """

    def __init__(self, groups: List[List[WorldDetection]]):
        super().__init__()
        self.groups = groups


class FusionManager(dai.node.ThreadedHostNode):
    def __init__(
        self,
        all_cam_extrinsics: Dict[str, Dict[str, Any]],
        fps: int,
        distance_threshold: float,
    ) -> None:
        super().__init__()

        self.fps = fps
        self.inputs: Dict[str, dai.Node.Input] = {}

        self.output = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.Buffer, True)
            ]
        )

        self.all_cam_extrinsics = all_cam_extrinsics
        for mxid in all_cam_extrinsics.keys():
            inp = self.createInput(
                name=mxid,
                group=mxid,
                queueSize=4,
                blocking=False,
                types=[
                    dai.Node.DatatypeHierarchy(
                        dai.DatatypeEnum.SpatialImgDetections, True
                    )
                ],
            )
            self.inputs[mxid] = inp

        self.detection_buffer: Dict[int, List[WorldDetection]] = (
            collections.defaultdict(list)
        )
        self.timestamp_queue: List[int] = []

        frame_time_ms = 1000 / self.fps  # time for one frame in milliseconds
        self.time_window_ms = (
            frame_time_ms * 0.8
        )  # time window for grouping near-simultaneous detections
        self.timeout = frame_time_ms / 1000  # timeout for fusion in seconds
        self.latest_device_timestamp_ms = 0

        self.distance_threshold_m = (
            distance_threshold  # Distance threshold for grouping detections in meters
        )

    def run(self):
        while self.isRunning():
            self._read_inputs()
            self._process_buffer()
            time.sleep(0.75 / self.fps)

    def _read_inputs(self):
        """Read all available detections from input queues and buffer them."""
        for mxid, inp in self.inputs.items():
            msg = inp.tryGet()
            if msg is None:
                continue

            assert isinstance(msg, dai.SpatialImgDetections)
            extrinsics = self.all_cam_extrinsics.get(mxid)
            if not extrinsics:
                continue

            world_dets = self._transform_detections_to_world(
                msg.detections, extrinsics["cam_to_world"], extrinsics["friendly_id"]
            )

            ts_ms = int(msg.getTimestamp().total_seconds() * 1000)
            self.latest_device_timestamp_ms = max(
                self.latest_device_timestamp_ms, ts_ms
            )

            self.detection_buffer[ts_ms].extend(world_dets)

            if ts_ms not in self.timestamp_queue:
                bisect.insort(self.timestamp_queue, ts_ms)

    def _process_buffer(self):
        """
        Process timestamps that are older than the fusion timeout,
        ensuring all relevant cameras have reported.
        """
        if not self.timestamp_queue:
            return

        oldest_ts_ms = self.timestamp_queue[0]

        if (self.latest_device_timestamp_ms - oldest_ts_ms) / 1000 > self.timeout:
            start_ts = self.timestamp_queue.pop(0)
            end_ts = start_ts + self.time_window_ms

            all_detections_in_window = self.detection_buffer.pop(start_ts, [])

            while self.timestamp_queue and self.timestamp_queue[0] <= end_ts:
                ts_to_pop = self.timestamp_queue.pop(0)
                all_detections_in_window.extend(
                    self.detection_buffer.pop(ts_to_pop, [])
                )

            if not all_detections_in_window:
                return

            groups = self._group_detections(all_detections_in_window)
            pruned_groups = self._prune_redundant_detections(groups)

            buffer = DetectionGroupBuffer(pruned_groups)
            buffer.setTimestamp(datetime.timedelta(milliseconds=start_ts))
            self.output.send(buffer)

    def _prune_redundant_detections(
        self, groups: List[List[WorldDetection]]
    ) -> List[List[WorldDetection]]:
        """
        For each group, ensure that each camera is represented by at most one detection
        (the one with the highest confidence).
        """
        pruned_groups = []
        for group in groups:
            # dictionary to track the best detection for each device within this group
            best_det_per_cam: Dict[int, WorldDetection] = {}

            for det in group:
                cam_id = det.camera_friendly_id
                if (
                    cam_id not in best_det_per_cam
                    or det.confidence > best_det_per_cam[cam_id].confidence
                ):
                    best_det_per_cam[cam_id] = det

            pruned_groups.append(list(best_det_per_cam.values()))

        return pruned_groups

    def _transform_detections_to_world(
        self,
        detections: List[dai.SpatialImgDetection],
        cam_to_world: np.ndarray,
        friendly_id: int,
    ) -> List[WorldDetection]:
        world_detections: List[WorldDetection] = []
        for det in detections:
            coords = det.spatialCoordinates

            # filter out ghost detections with z=0
            if coords.z == 0:
                continue

            # Convert from mm to m and add homogeneous w=1
            pos_cam = np.array(
                [coords.x / 1000.0, -coords.y / 1000.0, coords.z / 1000.0, 1.0]
            )
            pos_world = cam_to_world @ pos_cam.reshape(4, 1)

            world_detections.append(
                WorldDetection(
                    label=det.labelName,
                    confidence=det.confidence,
                    pos_world_homogeneous=pos_world,
                    camera_friendly_id=friendly_id,
                )
            )
        return world_detections

    def _group_detections(
        self, detections: List[WorldDetection]
    ) -> List[List[WorldDetection]]:
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
                    dist = np.linalg.norm(
                        dets[i].pos_world_homogeneous[:3]
                        - dets[j].pos_world_homogeneous[:3]
                    )
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
