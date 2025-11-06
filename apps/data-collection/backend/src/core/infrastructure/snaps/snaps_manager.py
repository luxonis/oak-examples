import depthai as dai
from box import Box
from depthai_nodes.node import SnapsProducer

from core.snapping.conditions_engine import ConditionsEngine
from core.snapping.conditions_factory import ConditionsFactory
from core.infrastructure.snaps.snaps_producer_factory import SnapsProducerFactory
from core.services.snap_collection_service import SnapCollectionService


class SnapsManager:
    """
    Facade for the snapping subsystem.
    """

    def __init__(
        self,
        pipeline: dai.Pipeline,
        input_node: dai.Node.Output,
        tracker: dai.node.ObjectTracker,
        detections: dai.ImgDetections,
        conditions_config: Box,
    ):
        self._pipeline = pipeline
        self._input_node = input_node
        self._tracker = tracker
        self._detections = detections
        self._conditions_config = conditions_config
        self._producer: SnapsProducer = None

        self._engine: ConditionsEngine = None

        self._build()

    def _build(self) -> "SnapsManager":
        cond_manager = ConditionsFactory(self._conditions_config)
        self._engine = cond_manager.get_engine()

        snaps_producer = SnapsProducerFactory.create(
            self._pipeline,
            self._input_node,
            self._tracker,
            self._detections,
            self._engine,
        )
        self._producer = snaps_producer
        self._snap_service = SnapCollectionService(self._engine, self._producer)
        return self

    def get_service(self) -> SnapCollectionService:
        return self._snap_service

    def get_engine(self):
        return self._engine
