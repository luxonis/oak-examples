from typing import (
    Generic,
    Optional,
    TypeVar,
)

import depthai as dai

from depthai_nodes import Collection
from depthai_nodes.logging import get_logger

TCollected = TypeVar("TCollected", bound=dai.Buffer)


class MessageCollector(dai.node.ThreadedHostNode, Generic[TCollected]):
    """Threaded host node that collects multiple data messages from a single input matched by timestamp.

    The node receives one input stream:

    - **data_input**: messages to be collected.

    For each reference timestamp, the node waits until the number of gathered
    data messages equals `wait_count_fn(reference)`. Once ready, it emits a
    :class:`depthai_nodes.Collection` message containing the gathered items.

    The default `wait_count_fn` uses ``len(reference.detections)``, which works
    out-of-the-box for messages that expose a ``detections`` attribute (e.g.
    ``dai.ImgDetections``).

    Inputs
    ------
    _data_input : dai.Node.Input
        Stream of data messages to be gathered (type ``TGathered``).

    Outputs
    -------
    out : dai.Node.Output
        Emits :class:`depthai_nodes.Collection` objects with:
        ``items`` (list of data).
    """

    def __init__(self) -> None:
        """Initializes the GatherData node."""
        super().__init__()
        self._camera_fps: Optional[int] = None

        self._data_input = self.createInput()
        self._out = self.createOutput()

        self._next_reference = None

        self._logger = get_logger(__name__)
        self._logger.debug("MessageCollector initialized")

    @property
    def out(self) -> dai.Node.Output:
        """Return the gathered output stream."""
        return self._out

    def setCameraFps(self, fps: int) -> None:
        """Set the camera frame rate used for timestamp matching.

        Parameters
        ----------
        fps
            Positive camera frame rate used for matching tolerance and polling.
        """
        if fps <= 0:
            raise ValueError(f"Camera FPS must be positive, got {fps}")
        self._camera_fps = fps
        self._logger.debug(f"Camera FPS set to {fps}")

    def build(
        self,
        cameraFps: int,
        inputData: dai.Node.Output,
    ) -> "MessageCollector[TCollected]":
        """Connect the data and reference streams used for gathering.

        Parameters
        ----------
        cameraFps
            Camera frame rate used to derive timestamp matching tolerance and
            polling interval.
        inputData
            Upstream output producing the data messages to gather.

        Returns
        -------
        Collection[TCollected]
            The configured node instance.
        """
        self.setCameraFps(cameraFps)
        inputData.link(self._data_input)
        self._logger.debug(f"GatherData built with cameraFps={cameraFps}")
        return self

    def run(self) -> None:
        """Poll both inputs, match messages by timestamp, and emit ready groups."""
        self._logger.debug("MessageCollector run started")
        if not self._camera_fps:
            raise ValueError(
                "Camera FPS not set. Call build() before starting the pipeline."
            )
        msg: TCollected = self._data_input.get()  # noqa
        current_msg_ts = self._get_total_seconds_ts(msg)
        collected = [msg]
        while self.isRunning():
            msg: TCollected = self._data_input.get()  # noqa
            msg_ts = self._get_total_seconds_ts(msg)
            if self._timestamps_in_tolerance(msg_ts, current_msg_ts):
                collected.append(msg)
            else:
                # skip old data
                if msg_ts < current_msg_ts:
                    continue
                else:
                    output_msg = Collection(
                        items=collected,
                    )
                    output_msg.setTimestampDevice(msg.getTimestampDevice())
                    output_msg.setTimestamp(msg.getTimestamp())
                    output_msg.setSequenceNum(msg.getSequenceNum())
                    self.out.send(output_msg)
                    current_msg_ts = msg_ts
                    collected.clear()
                    collected.append(msg)

    def _get_total_seconds_ts(self, buffer_like: dai.Buffer) -> float:
        return buffer_like.getTimestamp().total_seconds()

    def _timestamps_in_tolerance(self, timestamp1: float, timestamp2: float) -> bool:
        difference = abs(timestamp1 - timestamp2)
        return difference < (1 / self._camera_fps / 2)
