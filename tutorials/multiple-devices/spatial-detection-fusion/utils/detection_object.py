import numpy as np


class WorldDetection:
    """
    Represents a detected object's state in the world coordinate system,
    derived from a tracklet.
    """

    def __init__(
        self,
        label: str,
        pos_world_homogeneous: np.ndarray,  # 4x1: [x, y, z, 1].T
        camera_friendly_id: int,
        confidence: float = 0.0,
    ):
        self.label: str = label
        self.pos_world_homogeneous: np.ndarray = pos_world_homogeneous
        self.pos_world_cartesian: np.ndarray = pos_world_homogeneous[
            :3, 0
        ]  # Extract [x, y, z]
        self.camera_friendly_id: int = camera_friendly_id
        self.confidence: float = confidence

        self.corresponding_world_detections: list["WorldDetection"] = []

    def __repr__(self):
        return (
            f"WorldDetection lbl='{self.label}', "
            f"pos_w=({self.pos_world_cartesian[0]:.2f}, {self.pos_world_cartesian[1]:.2f}, {self.pos_world_cartesian[2]:.2f}), "
            f"cam_id={self.camera_friendly_id})"
        )
