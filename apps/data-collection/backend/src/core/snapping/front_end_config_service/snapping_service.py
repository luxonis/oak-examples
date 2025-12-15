from pydantic import ValidationError
from core.base_service import BaseService
from core.snapping.conditions.base_condition import Condition
from core.snapping.conditions.condition_key import ConditionKey
from core.snapping.front_end_config_service.snap_payload import SnapPayload
from core.service_name import ServiceName


class SnappingService(BaseService[SnapPayload]):
    """
    Handles updates to snapping conditions and manages SnapsProducer state.
    """

    NAME = ServiceName.SNAP_COLLECTION

    def __init__(self, conditions: dict[ConditionKey, Condition]):
        super().__init__()
        self._conditions: dict[ConditionKey, Condition] = conditions

    def handle(self, payload: SnapPayload) -> dict[str, any]:
        try:
            payload = SnapPayload.model_validate(payload)
        except ValidationError as e:
            return {"ok": False, "error": e.errors()}

        any_active = False
        for key, params in payload.root.items():
            cond = self._conditions.get(key)
            if not cond:
                continue
            cond.apply_config(params)
            any_active |= cond.enabled

        return {"ok": True, "active": any_active}
