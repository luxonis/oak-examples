import depthai as dai
import time

from core.snapping.conditions.base_condition import Condition
from core.snapping.conditions.condition_key import ConditionKey
from depthai_nodes.message import SnapData
import logging as log


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
        self._conditions: dict[ConditionKey, Condition] = {}

    def build(
        self,
        frame: dai.Node.Output,
        conditions: dict[ConditionKey, Condition],
        detections: dai.Node.Output,
        tracklets: dai.Node.Output,
    ):
        self._conditions = conditions
        self.link_args(frame, detections, tracklets)
        return self

    def process(
        self,
        frame: dai.ImgFrame,
        detections: dai.Buffer,
        tracklets: dai.Tracklets,
    ) -> None:
        assert isinstance(detections, dai.ImgDetections)
        for cond in self._conditions.values():
            if not cond.should_trigger(
                detections=detections.detections, tracklets=tracklets
            ):
                continue

            snap = SnapData(
                snap_name=cond.name,
                file_name=f"{cond.name}_{int(time.time())}",
                frame=frame,
                detections=detections,
                tags=cond.tags,
                extras=cond.make_extras(),
            )

            log.info(f"Produced snap for condition: {cond.name}")
            log.info(f"Detections: {detections.detections}")

            self.out.send(snap)
