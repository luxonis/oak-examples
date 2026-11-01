import cv2
import depthai as dai
import numpy as np


class StereoSGBM(dai.node.HostNode):
    """Match synchronized rectified frames supplied by StereoDepth."""

    def __init__(self):
        super().__init__()
        self.max_disparity = 96
        self.stereoProcessor = cv2.StereoSGBM_create(
            minDisparity=0,
            numDisparities=self.max_disparity,
            blockSize=5,
            P1=80,
            P2=800,
            disp12MaxDiff=5,
            mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY,
        )
        datatype = [dai.Node.DatatypeHierarchy(dai.DatatypeEnum.ImgFrame, True)]
        self.disparity_out = self.createOutput(possibleDatatypes=datatype)
        self.raw_disparity_out = self.createOutput(possibleDatatypes=datatype)

    def build(self, left: dai.Node.Output, right: dai.Node.Output) -> "StereoSGBM":
        self.link_args(left, right)
        return self

    def process(self, left: dai.ImgFrame, right: dai.ImgFrame) -> None:
        # Avoid comparing frames from different captures after a queue drop.
        if abs((left.getTimestamp() - right.getTimestamp()).total_seconds()) > 0.005:
            return
        left_img, right_img = left.getCvFrame(), right.getCvFrame()
        left_pad = cv2.copyMakeBorder(
            left_img, 0, 0, self.max_disparity, 0, cv2.BORDER_CONSTANT
        )
        right_pad = cv2.copyMakeBorder(
            right_img, 0, 0, self.max_disparity, 0, cv2.BORDER_CONSTANT
        )
        # OpenCV disparity has four fractional bits; retain them for SSIM.
        disparity = self.stereoProcessor.compute(left_pad, right_pad)[
            :, self.max_disparity :
        ]
        disparity = np.maximum(disparity, 0).astype(np.uint16)
        preview = np.clip(
            disparity * (255.0 / (16 * self.max_disparity)), 0, 255
        ).astype(np.uint8)
        color = cv2.applyColorMap(preview, cv2.COLORMAP_JET)
        self.disparity_out.send(self._frame(left, color, dai.ImgFrame.Type.BGR888i))
        self.raw_disparity_out.send(
            self._frame(left, disparity, dai.ImgFrame.Type.RAW16)
        )

    @staticmethod
    def _frame(source, pixels, frame_type):
        frame = dai.ImgFrame()
        frame.setCvFrame(pixels, frame_type)
        frame.setTimestamp(source.getTimestamp())
        frame.setTimestampDevice(source.getTimestampDevice())
        frame.setSequenceNum(source.getSequenceNum())
        frame.setTransformation(source.getTransformation())
        return frame
