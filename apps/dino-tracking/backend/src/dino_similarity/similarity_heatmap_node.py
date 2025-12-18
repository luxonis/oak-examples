import cv2
import depthai as dai
import numpy as np
from depthai_nodes.node import BaseHostNode

from dino_similarity.dino_grid_extractor_node import DinoGrid
from dino_similarity.reference_vectors.adaptive_reference_vector_node import (
    AdaptiveReferenceVectors,
    BestVectorMatch,
)


class SimilarityHeatmap(BaseHostNode):
    """
    A DepthAI node that computes a similarity heatmap using reference vectors.

    This node takes computes the similarity heatmap from reference vectors and a DINO grid.
    It then sends the heatmap and the best matching vector along with its similarity score for downstream processing.
    """

    def __init__(self):
        super().__init__()
        self._prev_heat: np.ndarray | None = None
        self._heatmap_smoothing_factor = 0.6

        self.vector_out: dai.Node.Output = self.createOutput()

    def build(
        self,
        reference_vectors_in: dai.Node.Output,
        grid_in: dai.Node.Output,
        frame_in: dai.Node.Output,
    ):
        self.link_args(reference_vectors_in, grid_in, frame_in)
        return self

    def process(
        self,
        reference_vectors_msg: dai.Buffer,
        dino_msg: dai.Buffer,
        frame_msg: dai.ImgFrame,
    ):
        assert isinstance(reference_vectors_msg, AdaptiveReferenceVectors)
        assert isinstance(dino_msg, DinoGrid)
        H, W = frame_msg.getCvFrame().shape[:2]

        if reference_vectors_msg.vector_init is None:
            heat = np.zeros((H, W), dtype=np.float32)
            self._send_heatmap(frame_msg, heat)

            dummy_vector = np.zeros(1, dtype=np.float32)
            self._send_best_vector(dummy_vector, 0.0, reference_vectors_msg)
            return

        grid = dino_msg.grid
        ref_init = reference_vectors_msg.vector_init
        ref_adapt = reference_vectors_msg.vector_adapt
        adaptation_strength = reference_vectors_msg.adaptation_strength

        cos_grid, best_vec, best_score = self._compute_similarity(
            grid, ref_init, ref_adapt, adaptation_strength
        )

        self._send_best_vector(best_vec, best_score, reference_vectors_msg)

        heat = self._produce_heatmap(cos_grid, (H, W))
        self._send_heatmap(frame_msg, heat)

    def _compute_similarity(
        self,
        grid: np.ndarray,
        reference_vector_init: np.ndarray,
        reference_vector_adapt: np.ndarray,
        adaptation_strength: float,
    ) -> tuple[np.ndarray, np.ndarray, float]:
        H, W, D = grid.shape
        feats = grid.reshape(-1, D).astype(np.float32)

        cos_init = feats @ reference_vector_init
        cos_adapt = feats @ reference_vector_adapt

        cos_combined = (
            adaptation_strength * cos_adapt + (1 - adaptation_strength) * cos_init
        )
        cos_grid = cos_combined.reshape(H, W).astype(np.float32)

        best_idx = int(np.argmax(cos_adapt))
        best_score = float(cos_adapt[best_idx])
        best_vector = self._normalize(feats[best_idx])

        return cos_grid, best_vector, best_score

    def _produce_heatmap(
        self, cos_grid: np.ndarray, frame_size: tuple[int, int]
    ) -> np.ndarray:
        H, W = frame_size

        heat = cv2.resize(cos_grid, (W, H), interpolation=cv2.INTER_LINEAR).astype(
            np.float32
        )
        heat = np.clip(heat, 0.0, 1.0)

        if np.any(heat > 0.0):
            if self._prev_heat is None or self._prev_heat.shape != heat.shape:
                blended = heat
            else:
                blended = (
                    self._heatmap_smoothing_factor * heat
                    + (1 - self._heatmap_smoothing_factor) * self._prev_heat
                )
        else:
            blended = np.zeros_like(heat)

        self._prev_heat = blended
        return blended

    @staticmethod
    def _normalize(v: np.ndarray) -> np.ndarray:
        return v / (np.linalg.norm(v) + 1e-8)

    def _send_best_vector(
        self, best_vec: np.ndarray, best_score: float, ref_msg: dai.Buffer
    ):
        best_vector = BestVectorMatch()
        best_vector.vector = best_vec
        best_vector.score = best_score

        best_vector.setSequenceNum(ref_msg.getSequenceNum())
        best_vector.setTimestamp(ref_msg.getTimestamp())
        best_vector.setTimestampDevice(ref_msg.getTimestampDevice())

        self.vector_out.send(best_vector)

    def _send_heatmap(self, reference_msg: dai.Buffer, heat: np.ndarray):
        heat_u8 = (heat * 255.0).astype(np.uint8)
        heat_bgr = cv2.merge([heat_u8, heat_u8, heat_u8])

        out = dai.ImgFrame()
        out.setCvFrame(heat_bgr, dai.ImgFrame.Type.BGR888i)
        out.setSequenceNum(reference_msg.getSequenceNum())
        out.setTimestamp(reference_msg.getTimestamp())
        out.setTimestampDevice(reference_msg.getTimestampDevice())

        self.out.send(out)
