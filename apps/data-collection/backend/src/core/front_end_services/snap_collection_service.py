from pydantic import ValidationError
from core.front_end_services.base_service import BaseService
from core.snapping.conditions_engine import ConditionsEngine
from depthai_nodes.node import SnapsProducer
from core.front_end_services.payloads.snap_payload import SnapPayload
from core.front_end_services.service_name import ServiceName


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
        self.engine: ConditionsEngine = engine
        self.snaps_producer: SnapsProducer = snaps_producer

    def handle(self, payload: SnapPayload) -> dict[str, any]:
        try:
            payload = SnapPayload.model_validate(payload)
        except ValidationError as e:
            return {"ok": False, "error": e.errors()}

        self.engine.import_conditions_config(payload.root)
        any_active = self.engine.any_active()
        self.snaps_producer.setRunning(any_active)

        return {"ok": True, "active": any_active}
