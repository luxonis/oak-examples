import depthai as dai
import numpy as np
from depthai_nodes.node import BaseHostNode


class DinoGrid(dai.Buffer):
    """
    Host-side message that carries an (H, W, D) float32 grid.
    """

    grid: np.ndarray | None = None


class DinoGridExtractor(BaseHostNode):
    """
    Handles Dino Grid Extraction from the DINO embeddings.

    This node processes the DINO embeddings received as input, extracts the feature grid,
    normalizes it, and sends it as output for downstream processing.
    """

    def build(
        self,
        dino_in: dai.Node.Output,
    ):
        self.link_args(dino_in)
        return self

    def process(self, dino_msg: dai.NNData):
        arr: np.ndarray = dino_msg.getTensor(
            "embeddings",
            dequantize=True,
            storageOrder=dai.TensorInfo.StorageOrder.NCHW,
        )
        feats = arr.transpose(0, 3, 1, 2)
        feats = feats.reshape(-1, feats.shape[3])
        feats /= np.linalg.norm(feats, axis=1, keepdims=True) + 1e-8

        grid = feats.reshape(arr.shape[3], arr.shape[1], arr.shape[2])

        out = DinoGrid()
        out.grid = grid

        out.setSequenceNum(dino_msg.getSequenceNum())
        out.setTimestamp(dino_msg.getTimestamp())
        out.setTimestampDevice(dino_msg.getTimestampDevice())

        self.out.send(out)
