import logging
import time
from typing import Callable

import depthai as dai
from PIL import Image
import cv2

LOGGER = logging.getLogger(__name__)


def _load_pyzbar_decoder():
    try:
        from pyzbar.pyzbar import decode as pyzbar_decode

        return pyzbar_decode, None
    except Exception as exc:
        return None, exc


def _load_zxing_decoder():
    try:
        import zxingcpp

        return zxingcpp, None
    except Exception as exc:
        return None, exc


_PYZBAR_DECODE, _PYZBAR_LOAD_ERROR = _load_pyzbar_decoder()
_ZXINGCPP, _ZXINGCPP_LOAD_ERROR = _load_zxing_decoder()


class BarcodeDecoder(dai.node.ThreadedHostNode):
    """
    Custom host node that receives ImgFrame messages,
    runs barcode decoding backends on the host and emits raw bytes
    in dai.Buffer messages.
    """

    _logged_backend_status = False

    def __init__(self):
        super().__init__()

        self.input = self.createInput()
        self.input.setPossibleDatatypes([(dai.DatatypeEnum.ImgFrame, True)])

        self.output = self.createOutput()
        self.output.setPossibleDatatypes([(dai.DatatypeEnum.Buffer, True)])

        if not BarcodeDecoder._logged_backend_status:
            if _PYZBAR_DECODE is None and _ZXINGCPP is None:
                LOGGER.warning(
                    "No barcode decoder backend is available. pyzbar failed to load (%s) "
                    "and zxing-cpp failed to load (%s). The example will run without host-side decoding.",
                    _PYZBAR_LOAD_ERROR,
                    _ZXINGCPP_LOAD_ERROR,
                )
            elif _PYZBAR_DECODE is None and _ZXINGCPP is not None:
                LOGGER.warning(
                    "pyzbar is unavailable (%s). Falling back to zxing-cpp for barcode decoding.",
                    _PYZBAR_LOAD_ERROR,
                )
            elif _ZXINGCPP is None and _PYZBAR_DECODE is not None:
                LOGGER.warning(
                    "zxing-cpp is unavailable (%s). Using pyzbar only for barcode decoding.",
                    _ZXINGCPP_LOAD_ERROR,
                )

            BarcodeDecoder._logged_backend_status = True

    def run(self):
        while self.isRunning():
            in_msg = self.input.tryGet()
            if in_msg is None:
                time.sleep(0.001)
                continue

            cv_frame = in_msg.getCvFrame()
            barcodes = decode_frame_with_available_backends(cv_frame)

            for barcode_data in barcodes:
                buf = dai.Buffer()
                buf.setData(barcode_data)
                self.output.send(buf)

            if not barcodes:
                time.sleep(0.001)


def decode_frame_with_available_backends(cv_frame) -> list[bytes]:
    decoders: list[tuple[str, Callable]] = []
    if _PYZBAR_DECODE is not None:
        decoders.append(("pyzbar", _decode_with_pyzbar))
    if _ZXINGCPP is not None:
        decoders.append(("zxing-cpp", _decode_with_zxing))

    for backend_name, decoder in decoders:
        try:
            decoded_payloads = decoder(cv_frame)
        except Exception as exc:
            LOGGER.warning("Barcode decoder backend '%s' failed: %s", backend_name, exc)
            continue

        if decoded_payloads:
            return decoded_payloads

    return []


def _decode_with_pyzbar(cv_frame) -> list[bytes]:
    if _PYZBAR_DECODE is None:
        return []

    pil_img = Image.fromarray(cv2.cvtColor(cv_frame, cv2.COLOR_BGR2RGB))
    barcodes = _PYZBAR_DECODE(pil_img)

    if not barcodes:
        for angle in (90, 180, 270):
            rotated = pil_img.rotate(angle, expand=True)
            barcodes = _PYZBAR_DECODE(rotated)
            if barcodes:
                break

    if not barcodes:
        inv_frame = cv2.bitwise_not(cv_frame)
        inv_pil = Image.fromarray(cv2.cvtColor(inv_frame, cv2.COLOR_BGR2RGB))
        barcodes = _PYZBAR_DECODE(inv_pil)

    return [bytes(barcode.data) for barcode in barcodes if barcode.data]


def _decode_with_zxing(cv_frame) -> list[bytes]:
    if _ZXINGCPP is None:
        return []

    barcodes = _ZXINGCPP.read_barcodes(
        cv_frame,
        try_rotate=True,
        try_invert=True,
    )
    return [bytes(barcode.bytes) for barcode in barcodes if barcode.bytes]
