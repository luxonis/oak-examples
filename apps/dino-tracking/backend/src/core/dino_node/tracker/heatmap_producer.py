import cv2
import numpy as np


class HeatmapProducer:
    """
    Turns cosine grid into a full-res heatmap and applies (currently
    disabled) temporal smoothing.

    Logic is kept identical to the original:
      - resize
      - clip to [0,1]
      - compute blended = a*cur + (1-a)*prev
      - then override blended = heat_clipped
    """

    def __init__(self):
        self.prev_heat: np.ndarray | None = None
        self.temporal_alpha: float = 0.6

    def reset(self) -> None:
        self.prev_heat = None

    def empty(self, frame_shape: tuple[int, int]) -> np.ndarray:
        H_full, W_full = frame_shape
        return np.zeros((H_full, W_full), dtype=np.float32)

    def from_cosine_grid(
        self,
        cos_grid: np.ndarray,
        frame_shape: tuple[int, int],
    ) -> np.ndarray:
        H_full, W_full = frame_shape

        heat_full = cv2.resize(
            cos_grid,
            (W_full, H_full),
            interpolation=cv2.INTER_LINEAR,
        ).astype(np.float32)

        heat_clipped = np.clip(heat_full, 0.0, 1.0).astype(np.float32)

        if np.any(heat_clipped > 0.0):
            if self.prev_heat is None or self.prev_heat.shape != heat_clipped.shape:
                blended = heat_clipped
            else:
                a = float(self.temporal_alpha)
                blended = a * heat_clipped + (1.0 - a) * self.prev_heat
        else:
            blended = np.zeros_like(heat_clipped, dtype=np.float32)


        self.prev_heat = blended
        return blended
