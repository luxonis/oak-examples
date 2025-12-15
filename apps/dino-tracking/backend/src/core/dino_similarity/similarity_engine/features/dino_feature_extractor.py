import numpy as np
import depthai as dai


class DinoFeatureExtractor:
    """
    Reads DINO NNData and returns an (H_grid, W_grid, D) grid
    of L2-normalized feature vectors.

    This is identical to the old _extract_patch_grid.
    """

    def extract_grid(self, nn_data: dai.NNData) -> np.ndarray:
        arr = nn_data.getTensor(
            "embeddings",
            dequantize=True,
            storageOrder=dai.TensorInfo.StorageOrder.NCHW,
        )
        feats = arr.transpose(0, 3, 1, 2)
        feats = feats.reshape(-1, feats.shape[3])

        feats /= np.linalg.norm(feats, axis=1, keepdims=True) + 1e-8

        return feats.reshape(arr.shape[3], arr.shape[1], arr.shape[2])
