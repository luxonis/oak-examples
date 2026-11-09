import depthai as dai
import numpy as np


class PlaneValidity(dai.Buffer):
    """Per-frame status of whether a valid ground-plane equation is available.

    `R` is the 3x3 camera-to-ground rotation matrix computed from IMU gravity.
    It rotates camera-frame points into a ground-aligned frame where y' is
    world-down and z' is forward projected onto the ground plane.
    """

    def __init__(
        self,
        plane_valid: bool,
        plane_eq: np.ndarray | None = None,
        R: np.ndarray | None = None,
    ):
        super().__init__()
        self.plane_valid = bool(plane_valid)
        self.plane_eq: np.ndarray
        self.R: np.ndarray
        if plane_eq is None:
            self.plane_eq = np.empty((0,), dtype=np.float32)
        else:
            self.plane_eq = np.asarray(plane_eq, dtype=np.float32).reshape(-1)
        if R is None:
            self.R = np.empty((0, 0), dtype=np.float32)
        else:
            self.R = np.asarray(R, dtype=np.float32).reshape(3, 3)
