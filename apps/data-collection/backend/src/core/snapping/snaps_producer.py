import depthai as dai
import time
from typing import Optional
from core.snapping.conditions_engine import ConditionsEngine
from depthai_nodes.message import SnapData


class SnapsProducer(dai.node.HostNode):
    """
    Host node that evaluates snapping conditions each pipeline tick and emits
    SnapData messages for downstream SnapsProducer.

    Attributes
    ----------
    _engine : ConditionsEngine
        Engine responsible for evaluating all registered snap conditions.
    """

    def __init__(self):
        super().__init__()
        self._engine: Optional[ConditionsEngine] = None

    def build(
        self,
        frame: dai.Node.Output,
        engine: ConditionsEngine,
        detections: dai.Node.Output,
        tracklets: dai.Node.Output,
    ):
        self._engine = engine
        self.link_args(frame, detections, tracklets)
        return self

    def process(
        self,
        frame: dai.ImgFrame,
        detections: dai.Buffer,
        tracklets: dai.Tracklets,
    ) -> None:
        assert isinstance(detections, dai.ImgDetections)
        conditions = self._engine.evaluate(
            detections=detections.detections, tracklets=tracklets
        )
        if not conditions:
            return

        for cond in conditions:
            snap = SnapData(
                snap_name=cond.name,
                file_name=f"{cond.name}_{int(time.time())}",
                frame=frame,
                detections=detections,
                tags=cond.tags,
                extras=cond.make_extras(),
            )

            self.out.send(snap)
