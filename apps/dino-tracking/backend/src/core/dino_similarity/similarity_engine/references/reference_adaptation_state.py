import numpy as np


class ReferenceAdaptationState:
    """
    Holds and updates:
      - reference_init (frozen)
      - reference_adapt (EMA-updated)
      - frame counters
      - adaptation rules (threshold, interval, blend)
    """

    def __init__(self):
        self.reference_init: np.ndarray = None
        self.reference_adapt: np.ndarray = None

        self.learn_thresh = 0.85
        self.learn_interval = 30
        self.learn_blend = 0.3
        self.combine_alpha = 0.7

        self.frame_idx = 0
        self.last_learn_frame = -(10**9)

    def tick(self):
        self.frame_idx += 1

    def reset(self):
        self.reference_init = None
        self.reference_adapt = None
        self.frame_idx = 0
        self.last_learn_frame = -(10**9)

    def has_reference(self) -> bool:
        return self.reference_init is not None and self.reference_adapt is not None

    def initialize(self, ref_embedding: np.ndarray):
        if ref_embedding is None:
            return

        self.reference_init = ref_embedding.copy()
        self.reference_adapt = ref_embedding.copy()

    def update_adapting_reference(self, best_vector: np.ndarray, best_value: float):
        if (
            best_value >= self.learn_thresh
            and (self.frame_idx - self.last_learn_frame) >= self.learn_interval
        ):
            beta = self.learn_blend

            updated = (1.0 - beta) * self.reference_adapt + beta * best_vector
            updated = updated / (np.linalg.norm(updated) + 1e-8)

            self.reference_adapt = updated.astype(np.float32)
            self.last_learn_frame = self.frame_idx
