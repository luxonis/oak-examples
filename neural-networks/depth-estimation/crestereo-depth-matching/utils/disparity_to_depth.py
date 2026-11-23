import depthai as dai
import numpy as np


def disparity_to_depth(disparity_px, baseline_mm, focal_length_px):
    """Convert horizontal pixel disparity to uint16 millimeters; zero means invalid."""
    if (
        not np.isfinite(baseline_mm)
        or baseline_mm <= 0
        or not np.isfinite(focal_length_px)
        or focal_length_px <= 0
    ):
        raise ValueError(
            "Positive calibrated baseline and rectified focal length are required"
        )
    disparity_px = np.asarray(disparity_px, dtype=np.float64)
    depth_mm = np.zeros(disparity_px.shape, dtype=np.uint16)
    valid = np.isfinite(disparity_px) & (disparity_px > 0.01)
    depth_mm[valid] = np.clip(
        baseline_mm * focal_length_px / disparity_px[valid], 0, 65535
    ).astype(np.uint16)
    return depth_mm


class DisparityToDepth(dai.node.HostNode):
    def __init__(self) -> None:
        super().__init__()
        self.output = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.ImgFrame, True)
            ]
        )

    def build(
        self,
        disparity: dai.Node.Output,
        baseline_mm: float,
        rectified: dai.Node.Output,
    ) -> "DisparityToDepth":
        self.link_args(disparity, rectified)
        self.baseline_mm = baseline_mm
        return self

    def process(self, disparity: dai.Buffer, rectified: dai.Buffer) -> None:
        assert isinstance(rectified, dai.ImgFrame)
        assert isinstance(disparity, dai.beta.Map2D), f"got type: {type(disparity)}"
        if disparity.getSequenceNum() != rectified.getSequenceNum():
            return
        focal_length_px = rectified.getTransformation().getIntrinsicMatrix()[0][0]
        disparity_frame = disparity.getMap().astype(np.float32)
        if disparity_frame.shape != (rectified.getHeight(), rectified.getWidth()):
            raise ValueError(
                "Model disparity must use rectified input pixel units and dimensions"
            )
        depth_mm = disparity_to_depth(
            disparity_frame, self.baseline_mm, focal_length_px
        )

        depth_frame = dai.ImgFrame()
        depth_frame.setFrame(depth_mm)
        depth_frame.setWidth(depth_mm.shape[1])
        depth_frame.setHeight(depth_mm.shape[0])
        depth_frame.setType(dai.ImgFrame.Type.RAW16)
        depth_frame.setTimestamp(disparity.getTimestamp())
        depth_frame.setSequenceNum(disparity.getSequenceNum())
        depth_frame.setTimestampDevice(rectified.getTimestampDevice())
        depth_frame.setTransformation(rectified.getTransformation())
        self.output.send(depth_frame)
