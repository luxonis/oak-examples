import depthai as dai
import numpy as np


class OccupancyMask(dai.Buffer):
    """Polar-grid occupancy, with range rows and angle columns."""

    def __init__(self, mask: np.ndarray):
        super().__init__()
        self.mask: np.ndarray = mask
