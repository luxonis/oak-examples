from pathlib import Path

import numpy as np

from constants.yml_constants_loader import YamlFileLoader


class ReferenceAdaptationState:
    """
    Holds and updates:
      - reference_init (frozen)
      - reference_adapt (EMA-updated)
      - frame counters
      - adaptation rules (threshold, interval, blend)
    """

    def __init__(self):
        constants = YamlFileLoader(Path(__file__).parent.parent.parent.parent.parent / "constants")
        consts = constants.load("dino_adaptation.yaml")
        self.reference_init: np.ndarray = None
        self.reference_adapt: np.ndarray = None

        self.learn_thresh = consts.learn_thresh
        self.learn_interval = consts.learn_interval
        self.learn_blend = consts.learn_blend
        self.combine_alpha = consts.combine_alpha

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
