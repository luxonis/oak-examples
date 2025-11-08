import depthai as dai
from box import Box
from depthai_nodes.node import SnapsProducer

from core.snapping.conditions_engine import ConditionsEngine
from core.snapping.conditions_factory import ConditionsFactory
from core.snapping.snaps_producer_factory import SnapsProducerFactory
from core.front_end_services.snap_collection_service import SnapCollectionService


class SnappingServiceManager:
    """
    Facade for the snapping subsystem.
    """

    def __init__(
        self,
        pipeline: dai.Pipeline,
        video_node: dai.Node.Output,
        tracker: dai.node.ObjectTracker,
        detections: dai.ImgDetections,
        conditions_config: Box,
    ):
        self._pipeline = pipeline
        self._video_node = video_node
        self._tracker = tracker
        self._detections = detections
        self._conditions_config = conditions_config
        self._producer: SnapsProducer = None

        self._engine: ConditionsEngine = None
        self._snap_service: SnapCollectionService = None

    def build(self):
        cond_factory = ConditionsFactory(self._conditions_config)
        self._engine = cond_factory.build_engine()

        snaps_producer = SnapsProducerFactory.create(
            self._pipeline,
            self._video_node,
            self._tracker,
            self._detections,
            self._engine,
        )
        self._producer = snaps_producer

        self._snap_service = SnapCollectionService(self._engine, self._producer)

    def register_service(self, visualizer: dai.RemoteConnection):
        visualizer.registerService(self._snap_service.name, self._snap_service.handle)

    def get_engine(self):
        return self._engine
