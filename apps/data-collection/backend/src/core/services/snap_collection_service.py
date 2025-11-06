from core.services.base_service import BaseService
from core.snapping.conditions_engine import ConditionsEngine
from depthai_nodes.node import SnapsProducer
from core.services.payloads.snap_payload import SnapPayload
from core.services.service_name import ServiceName


class SnapCollectionService(BaseService[SnapPayload]):
    """
    Handles updates to snapping conditions and manages SnapsProducer state.
    """

    NAME = ServiceName.SNAP_COLLECTION

    def __init__(
        self,
        engine: ConditionsEngine,
        snaps_producer: SnapsProducer,
    ):
        super().__init__()
        self.engine = engine
        self.snaps_producer = snaps_producer

    def handle(self, payload: SnapPayload) -> dict[str, any]:
        self.engine.import_conditions_config(payload)

        any_active = self.engine.any_active()

        self.snaps_producer.setRunning(any_active)

        return {"ok": True, "active": any_active}
