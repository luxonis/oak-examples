from pydantic import ValidationError
from core.front_end_services.base_service import BaseService
from core.snapping.conditions_engine import ConditionsEngine
from core.front_end_services.payloads.snap_payload import SnapPayload
from core.front_end_services.service_name import ServiceName


class SnappingService(BaseService[SnapPayload]):
    """
    Handles updates to snapping conditions and manages SnapsProducer state.
    """

    NAME = ServiceName.SNAP_COLLECTION

    def __init__(
        self,
        engine: ConditionsEngine
    ):
        super().__init__()
        self.engine: ConditionsEngine = engine

    def handle(self, payload: SnapPayload) -> dict[str, any]:
        try:
            payload = SnapPayload.model_validate(payload)
        except ValidationError as e:
            return {"ok": False, "error": e.errors()}

        self.engine.import_conditions_config(payload.root)
        any_active = self.engine.any_active()

        return {"ok": True, "active": any_active}
