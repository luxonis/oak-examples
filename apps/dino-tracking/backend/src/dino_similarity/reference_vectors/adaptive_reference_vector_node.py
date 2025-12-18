from typing import Optional

import depthai as dai
import numpy as np
from box import Box

from dino_similarity.reference_vectors.reference_vector_from_selection_node import (
    InitVectors,
)


class AdaptiveReferenceVectors(dai.Buffer):
    """
    A custom DepthAI buffer to hold reference vectors and blending parameters.
    """

    vector_init: Optional[np.ndarray] = None
    vector_adapt: Optional[np.ndarray] = None
    adaptation_strength: float = 0.7


class BestVectorMatch(dai.Buffer):
    """
    A custom DepthAI buffer to hold the best vector match on a new frame and its associated score.
    """

    vector: np.ndarray
    score: float


class AdaptiveReferenceVector(dai.node.ThreadedHostNode):
    """
    A DepthAI node for managing reference vectors with adaptive updates.

    This node processes input vectors and feedback to maintain and update
    reference vectors. It outputs the current references for downstream use.
    """

    def __init__(self, config: Box):
        super().__init__()

        self._vector_init: Optional[np.ndarray] = None
        self._vector_adapt: Optional[np.ndarray] = None
        self._last_vectors: Optional[np.ndarray] = None

        self._learn_thresh = config.learn_thresh
        self._learn_interval = config.learn_interval
        self._learn_blend = config.learn_blend
        self._adaptation_strength = config.adaptation_strength

        self._frame_idx = 0
        self._last_learn_frame = -self._learn_interval

        self.init_input = self.createInput("init", waitForMessage=True)
        self.feedback_input = self.createInput("feedback", waitForMessage=False)
        self.out = self.createOutput("references")

    def run(self):
        while self.isRunning():
            init_msg: InitVectors = self.init_input.get()

            if feedback_msg := self.feedback_input.tryGet():
                assert isinstance(feedback_msg, BestVectorMatch)
                self._frame_idx += 1
                if feedback_msg.vector is not None and self._vector_adapt is not None:
                    self._try_update_adaptive(feedback_msg.vector, feedback_msg.score)

            if self._vectors_changed(init_msg.vectors):
                self._reset()
                self._last_vectors = (
                    init_msg.vectors.copy() if init_msg.vectors is not None else None
                )

                if init_msg.vectors is not None:
                    self._initialize(init_msg.vectors)

            self._send_reference_vectors(init_msg)

    def _vectors_changed(self, vectors: Optional[np.ndarray]) -> bool:
        if self._last_vectors is None:
            return vectors is not None and len(vectors) > 0
        if vectors is None or len(vectors) == 0:
            return True
        return not np.array_equal(vectors, self._last_vectors)

    def _initialize(self, vectors: np.ndarray):
        if len(vectors) == 0:
            return

        ref = vectors.mean(axis=0)
        ref = ref / (np.linalg.norm(ref) + 1e-8)

        self._vector_init = ref.astype(np.float32)
        self._vector_adapt = ref.astype(np.float32)
        self._frame_idx = 0
        self._last_learn_frame = -self._learn_interval

    def _reset(self):
        self._vector_init = None
        self._vector_adapt = None
        self._frame_idx = 0
        self._last_learn_frame = -self._learn_interval

    def _try_update_adaptive(self, best_vector: np.ndarray, best_score: float):
        if best_score < self._learn_thresh:
            return
        if (self._frame_idx - self._last_learn_frame) < self._learn_interval:
            return

        beta = self._learn_blend
        updated = (1.0 - beta) * self._vector_adapt + beta * best_vector
        updated = updated / (np.linalg.norm(updated) + 1e-8)

        self._vector_adapt = updated.astype(np.float32)
        self._last_learn_frame = self._frame_idx

    def _send_reference_vectors(self, ref_msg: dai.Buffer):
        out = AdaptiveReferenceVectors()
        out.vector_init = self._vector_init
        out.vector_adapt = self._vector_adapt
        out.adaptation_strength = self._adaptation_strength

        out.setSequenceNum(ref_msg.getSequenceNum())
        out.setTimestamp(ref_msg.getTimestamp())
        out.setTimestampDevice(ref_msg.getTimestampDevice())

        self.out.send(out)
