import depthai as dai

import numpy as np
import cv2


class BlackFrame(dai.node.HostNode):
    """"""

    def __init__(self):
        super().__init__()
        self._pipeline = self.getParentPipeline()
        self.black_image = cv2.cvtColor(
            np.zeros((320, 320, 3), dtype=np.uint8), cv2.COLOR_RGB2BGR
        )
        cv2.putText(
            self.black_image,
            "No Head Detected",
            (15, 180),
            cv2.FONT_HERSHEY_TRIPLEX,
            0.9,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )

    def build(self, node_out: dai.Node.Output) -> "BlackFrame":
        self.link_args(node_out)
        self.sendProcessingToPipeline(True)
        return self

    def process(self, _any: dai.Buffer) -> None:
        black_img_frame = dai.ImgFrame()
        height, width, _ = self.black_image.shape
        black_img_frame.setData(self.black_image)
        black_img_frame.setType(dai.ImgFrame.Type.BGR888i)
        black_img_frame.setWidth(width)
        black_img_frame.setHeight(height)
        black_img_frame.setTimestamp(_any.getTimestamp())
        black_img_frame.setSequenceNum(_any.getSequenceNum())
        black_img_frame.setTimestampDevice(_any.getTimestampDevice())
        self.out.send(black_img_frame)
