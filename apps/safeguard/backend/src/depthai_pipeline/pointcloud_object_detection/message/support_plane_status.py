import depthai as dai
import numpy as np
from depthai_nodes.message import SupportPlane


class SupportPlaneStatus(dai.Buffer):
    """Per-frame support plane, valid while automatic calibration holds a passed plane.

    It is a Python ``Buffer`` subclass, so it travels between host nodes only.

    Args:
        plane: The support plane in camera millimeters, or ``None`` when invalid.
        R: 3x3 rotation from the camera frame to the support-plane-aligned frame,
            given exactly when ``plane`` is.

    Raises:
        ValueError: If only one of ``plane`` and ``R`` is given.
    """

    def __init__(
        self, plane: SupportPlane | None = None, R: np.ndarray | None = None
    ) -> None:
        super().__init__()
        if (plane is None) != (R is None):
            raise ValueError("plane and R must be given together")
        self.valid = plane is not None
        self.plane = plane
        self.R = (
            np.empty((0, 0), dtype=np.float32)
            if R is None
            else np.asarray(R, dtype=np.float32).reshape(3, 3)
        )
