import depthai as dai
from box import Box

from core.snapping.conditions.base_condition import Condition
from core.snapping.conditions.condition_key import ConditionKey
from core.snapping.conditions_factory import ConditionsFactory
from core.snapping.snaps_producer import SnapsProducer
from core.snapping.front_end_config_service.snapping_service import SnappingService

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

        self._conditions: dict[ConditionKey, Condition] = None
        self._snap_service: SnappingService = None

    def build(self):
        self._conditions = ConditionsFactory.build_conditions_from_yaml(
            self._conditions_config
        )

        producer = self._pipeline.create(SnapsProducer).build(
            self._video_node,
            self._conditions,
            self._detections.out,
            self._tracker.out,
        )

        self._uploader = self._pipeline.create(SnapsUploader).build(producer.out)

        self._snap_service = SnappingService(self._conditions)

    def register_service(self, visualizer: dai.RemoteConnection):
        visualizer.registerService(self._snap_service.name, self._snap_service.handle)

    def get_conditions(self) -> dict[ConditionKey, Condition]:
        return self._conditions
