from dataclasses import dataclass

import numpy as np
import depthai as dai


@dataclass
class BoundingBox:
    """2D bounding box in the image space, normalized to [0, 1]."""

    x_min: float
    y_min: float
    x_max: float
    y_max: float


@dataclass(slots=True)
class Obstacle:
    """One connected obstacle with a normalized box and nearest 3D point.

    Point coordinates are ground-aligned millimeters. ``nearest_point_depth``
    is forward z distance; ``nearest_point_radial`` is planar x/z range.
    """

    id: int
    bbox: BoundingBox
    nearest_point_xyz: np.ndarray
    nearest_point_depth: float
    nearest_point_radial: float


class Obstacles(dai.Buffer):
    """Detected obstacles sorted by forward distance, nearest first."""

    def __init__(self, obstacles: list[Obstacle]):
        super().__init__()
        self.obstacles = obstacles
