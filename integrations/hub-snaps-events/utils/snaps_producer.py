import depthai as dai
from depthai_nodes.message import SnapData

import time


class SnapsProducer(dai.node.HostNode):
    """
    Host node that evaluates snapping conditions each pipeline tick and emits
    SnapData messages for downstream SnapsProducer.

    Attributes
    ----------
    _conditions : dict[ConditionKey, Condition]
        A dictionary mapping condition keys to their respective snapping conditions.
    """

    def __init__(self):
        super().__init__()
        self._last_sent = time.time()
        self._time_interval = None

    def build(
        self,
        frame: dai.Node.Output,
        detections: dai.Node.Output,
        time_interval: float,
    ):
        self._time_interval = time_interval
        self.link_args(frame, detections)
        return self

    def process(
        self,
        frame: dai.Buffer,
        detections: dai.Buffer,
    ) -> None:
        assert isinstance(frame, dai.ImgFrame)
        assert isinstance(detections, dai.ImgDetections)

        if len(detections.detections) == 0:
            return

        if time.time() - self._last_sent >= self._time_interval:
            snap = SnapData(
                snap_name="test_snap",
                file_name=None,
                frame=frame,
                detections=detections,
                tags=["test_tag"],
                extras={"extra_key": "extra_value"},
            )
            self.out.send(snap)
            print("Snap sent")
            self._last_sent = time.time()
