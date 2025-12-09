import time
import depthai as dai
from PIL import Image
from pyzbar.pyzbar import decode
import cv2


class BarcodeDecoder(dai.node.ThreadedHostNode):
    """
    Custom host node that receives ImgFrame messages,
    runs pyzbar (plus optional fallbacks), and emits raw bytes
    in dai.Buffer messages.
    """

    def __init__(self):
        super().__init__()

        self.input = self.createInput()
        self.input.setPossibleDatatypes([(dai.DatatypeEnum.ImgFrame, True)])

        self.output = self.createOutput()
        self.output.setPossibleDatatypes([(dai.DatatypeEnum.Buffer, True)])

    def run(self):
        while self.isRunning():
            in_msg = self.input.tryGet()
            if in_msg is None:
                time.sleep(0.001)
                continue

            cv_frame = in_msg.getCvFrame()
            pil_img = Image.fromarray(cv2.cvtColor(cv_frame, cv2.COLOR_BGR2RGB))

            barcodes = decode(pil_img)

            if not barcodes:
                for angle in (90, 180, 270):
                    rotated = pil_img.rotate(angle, expand=True)
                    barcodes = decode(rotated)
                    if barcodes:
                        break

            if not barcodes:
                inv_frame = cv2.bitwise_not(cv_frame)
                inv_pil = Image.fromarray(cv2.cvtColor(inv_frame, cv2.COLOR_BGR2RGB))
                barcodes = decode(inv_pil)

            for bc in barcodes:
                buf = dai.Buffer()
                buf.setData(bc.data)
                self.output.send(buf)

            if not barcodes:
                time.sleep(0.001)
