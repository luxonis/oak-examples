import depthai as dai
from box import Box

from core.snapping.conditions_engine import ConditionsEngine
from core.snapping.conditions_factory import ConditionsFactory
from core.snapping.snaps_producer import SnapsProducer
from core.front_end_services.snapping_service import SnappingService

from depthai_nodes.node import ImgDetectionsBridge

from depthai_nodes.node import SnapsUploader


class SnappingServiceManager:
    """
    Facade for the snapping subsystem.
    """

    def __init__(
        self,
        pipeline: dai.Pipeline,
        video_node: dai.Node.Output,
        tracker: dai.node.ObjectTracker,
        detections: ImgDetectionsBridge,
        conditions_config: Box,
    ):
        self._pipeline = pipeline
        self._video_node = video_node
        self._tracker = tracker
        self._detections = detections
        self._conditions_config = conditions_config
        self._uploader: SnapsUploader = None

        self._engine: ConditionsEngine = None
        self._snap_service: SnappingService = None

    def build(self):
        cond_factory = ConditionsFactory(self._conditions_config)
        self._engine = cond_factory.build_engine()

        collector = self._pipeline.create(SnapsProducer).build(
            self._video_node,
            self._engine,
            self._detections.out,
            self._tracker.out,
        )

        self._uploader = self._pipeline.create(SnapsUploader).build(collector.out)

        self._snap_service = SnappingService(self._engine)

    def register_service(self, visualizer: dai.RemoteConnection):
        visualizer.registerService(self._snap_service.name, self._snap_service.handle)

    def get_engine(self):
        return self._engine
