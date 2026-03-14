from pydantic import BaseModel

from base_service import BaseService
from qr_scan.qr_decoder import QRDecoder


class QRConfigPayload(BaseModel):
    state: bool = False


class QRConfigService(BaseService[QRConfigPayload]):
    NAME = "QR Config Service"
    PAYLOAD_MODEL = QRConfigPayload

    def __init__(self, qr_decoder: QRDecoder):
        self._qr_decoder = qr_decoder

    def handle_typed(self, payload: QRConfigPayload) -> dict:
        self._qr_decoder.set_decode(payload.state)
        return {"ok": True}
