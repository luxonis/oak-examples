import cv2
import numpy as np
import depthai as dai

from depthai_nodes.node import BaseHostNode
from core.dino_similarity.vector_manager import VectorManager


class SimilarityHeatmapNode(BaseHostNode):
    """
    Computes similarity heatmap using references from VectorManager.

    Input: dino_embeddings, sync_message (from ReferenceNode)
    Output: similarity heatmap
    """

    def __init__(self):
        super().__init__()
        self._manager: VectorManager | None = None
        self._prev_heat: np.ndarray | None = None
        self._temporal_alpha = 0.6

    def build(
            self,
            manager: VectorManager,
            grid: dai.Node.Output,
            frame_in: dai.Node.Output,
    ):
        self._manager = manager
        self.link_args(grid, frame_in)
        return self

    def process(self, dino_msg: dai.Buffer, frame_msg: dai.ImgFrame):
        self._manager.tick()

        H, W = frame_msg.getCvFrame().shape[:2]

        if not self._manager.has_reference():
            heat = np.zeros((H, W), dtype=np.float32)
            self._send_heatmap(frame_msg, heat)
            return

        grid = dino_msg.grid

        ref_init, ref_adapt = self._manager.get_references()

        cos_grid, best_vec, best_score = self._compute_similarity(
            grid, ref_init, ref_adapt, self._manager.combine_alpha
        )

        self._manager.try_update_adaptive(best_vec, best_score)

        heat = self._produce_heatmap(cos_grid, (H, W))

        self._send_heatmap(frame_msg, heat)

    def _compute_similarity(
            self,
            grid: np.ndarray,
            reference_init: np.ndarray,
            reference_adapt: np.ndarray,
            alpha: float,
    ) -> tuple[np.ndarray, np.ndarray, float]:
        H, W, D = grid.shape
        feats = grid.reshape(-1, D).astype(np.float32)

        cos_init = feats @ reference_init
        cos_adapt = feats @ reference_adapt

        cos_combined = alpha * cos_adapt + (1 - alpha) * cos_init
        cos_grid = cos_combined.reshape(H, W).astype(np.float32)

        best_idx = int(np.argmax(cos_adapt))
        best_score = float(cos_adapt[best_idx])
        best_vector = self._normalize(feats[best_idx])

        return cos_grid, best_vector, best_score

    def _produce_heatmap(self, cos_grid: np.ndarray, frame_size: tuple[int, int]) -> np.ndarray:
        H, W = frame_size

        heat = cv2.resize(cos_grid, (W, H), interpolation=cv2.INTER_LINEAR).astype(np.float32)
        heat = np.clip(heat, 0.0, 1.0)

        if np.any(heat > 0.0):
            if self._prev_heat is None or self._prev_heat.shape != heat.shape:
                blended = heat
            else:
                blended = self._temporal_alpha * heat + (1 - self._temporal_alpha) * self._prev_heat
        else:
            blended = np.zeros_like(heat)

        self._prev_heat = blended
        return blended

    @staticmethod
    def _normalize(v: np.ndarray) -> np.ndarray:
        return v / (np.linalg.norm(v) + 1e-8)

    def _send_heatmap(self, reference_msg: dai.Buffer, heat: np.ndarray):
        heat_u8 = (heat * 255.0).astype(np.uint8)
        heat_bgr = cv2.merge([heat_u8, heat_u8, heat_u8])

        out = dai.ImgFrame()
        out.setCvFrame(heat_bgr, dai.ImgFrame.Type.BGR888i)
        out.setSequenceNum(reference_msg.getSequenceNum())
        out.setTimestamp(reference_msg.getTimestamp())
        out.setTimestampDevice(reference_msg.getTimestampDevice())
        self.out.send(out)
