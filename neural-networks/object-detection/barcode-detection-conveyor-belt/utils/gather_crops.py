from collections import deque
from time import monotonic, sleep

import depthai as dai
from depthai_nodes import GatheredData
from depthai_nodes.node import GatherData


class GatherCrops(GatherData):
    """Gather in source order, dropping incomplete frames after a bounded wait."""

    TIMEOUT_SECONDS = 2.0
    MAX_PENDING_FRAMES = 64

    def run(self) -> None:
        self._arrived_at = {}
        self._finished_timestamp = float("-inf")
        self._unmatched_data = deque(maxlen=self.MAX_PENDING_FRAMES)
        while self.isRunning():
            try:
                for queue, is_reference in (
                    (self._reference_input, True),
                    (self._data_input, False),
                ):
                    message = queue.tryGet()
                    if message is None:
                        continue
                    timestamp = self._get_total_seconds_ts(message)
                    if timestamp <= self._finished_timestamp:
                        continue
                    if is_reference:
                        self._arrived_at.setdefault(timestamp, monotonic())
                        self._add_reference(message)
                    else:
                        self._add_data(message)
            except dai.MessageQueue.QueueException:
                break
            # Poll even with idle inputs so the final incomplete frame can expire.
            self._send_ready_data()
            sleep(1 / self.INPUT_CHECKS_PER_FPS / self._camera_fps)

    def _send_ready_data(self) -> None:
        # GatherData's ready queue allows empty frames to overtake pending crops.
        while not self._ready_timestamps.empty():
            self._ready_timestamps.get()
        now = monotonic()
        while self._reference_data:
            timestamp = min(self._reference_data)
            ready = self._timestamp_ready(timestamp)
            if (
                not ready
                and now - self._arrived_at[timestamp] < self.TIMEOUT_SECONDS
                and len(self._reference_data) <= self.MAX_PENDING_FRAMES
            ):
                break
            reference = self._reference_data.pop(timestamp)
            items = self._data_by_reference_ts.pop(timestamp, [])
            self._arrived_at.pop(timestamp)
            self._finished_timestamp = timestamp
            self._clear_unmatched_data(timestamp)
            if ready:
                self.out.send(GatheredData(reference_data=reference, items=items))
            else:
                # Partial lists would shift detection/parent indices downstream.
                self._logger.warning(
                    "Dropping incomplete crop group for sequence %s",
                    reference.getSequenceNum(),
                )
