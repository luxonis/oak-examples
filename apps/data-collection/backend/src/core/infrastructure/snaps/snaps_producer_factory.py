from functools import partial
from depthai_nodes.node import SnapsProducer2Buffered, SnapsProducer

from core.snapping.conditions_engine import ConditionsEngine
from core.snapping.custom_snap_process import process_snaps
import depthai as dai
from depthai_nodes.node import ImgDetectionsBridge


class SnapsProducerFactory:
    @staticmethod
    def create(
        pipeline: dai.Pipeline,
        input_node: dai.Node.Output,
        tracker: dai.node.ObjectTracker,
        detections: ImgDetectionsBridge,
        engine: ConditionsEngine,
    ) -> SnapsProducer:
        return pipeline.create(SnapsProducer2Buffered).build(
            frame=input_node,
            msg=tracker.out,
            msg2=detections.out,
            running=False,
            process_fn=partial(process_snaps, engine=engine),
        )
