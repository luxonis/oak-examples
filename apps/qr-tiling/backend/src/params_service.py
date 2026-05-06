from collections.abc import Callable

from base_service import BaseService
from qr_scan.qr_decoder import QRDecoder


class CurrentParamsService(BaseService[None]):
    NAME = "Get Current Params Service"
    PAYLOAD_MODEL = None

    def __init__(
        self,
        current_tiling_params: Callable[[], dict],
        qr_decoder: QRDecoder,
    ):
        self._current_tiling_params = current_tiling_params
        self._decoder = qr_decoder

    def handle_typed(self, payload: None = None) -> dict:
        return {
            "tiling": self._current_tiling_params(),
            "decoder": self._decoder.decode_enabled,
        }
