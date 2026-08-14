import depthai as dai
import numpy as np

import depthai_nodes


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
        focal_length_px: float,
    ) -> "DisparityToDepth":
        self.link_args(disparity)
        self.baseline_mm = baseline_mm
        self.focal_length_px = focal_length_px
        return self

    def process(self, disparity: dai.Buffer) -> None:
        assert isinstance(
            disparity, depthai_nodes.Map2D
        ), f"got type: {type(disparity)}"
        disparity_frame = disparity.map.astype(np.float32)
        depth_mm = np.zeros(disparity_frame.shape, dtype=np.uint16)

        valid = disparity_frame > 0
        depth_values = (self.baseline_mm * self.focal_length_px) / disparity_frame[
            valid
        ]
        depth_mm[valid] = np.clip(depth_values, 0, np.iinfo(np.uint16).max).astype(
            np.uint16
        )

        depth_frame = dai.ImgFrame()
        depth_frame.setFrame(depth_mm)
        depth_frame.setWidth(depth_mm.shape[1])
        depth_frame.setHeight(depth_mm.shape[0])
        depth_frame.setType(dai.ImgFrame.Type.RAW16)
        depth_frame.setTimestamp(disparity.getTimestamp())
        depth_frame.setSequenceNum(disparity.getSequenceNum())
        self.output.send(depth_frame)
