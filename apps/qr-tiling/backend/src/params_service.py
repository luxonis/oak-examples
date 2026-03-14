from base_service import BaseService
from qr_scan.qr_decoder import QRDecoder
from tiling.dynamic_tiling import DynamicTiling


class CurrentParamsService(BaseService[None]):
    NAME = "Get Current Params Service"
    PAYLOAD_MODEL = None

    def __init__(
        self,
        dynamic_tiling: DynamicTiling,
        qr_decoder: QRDecoder,
    ):
        self._dynamic_tiling = dynamic_tiling
        self._decoder = qr_decoder

    def handle_typed(self, payload: None = None) -> dict:
        return {
            "tiling": self._dynamic_tiling.current_params,
            "decoder": self._decoder.decode_enabled,
        }
