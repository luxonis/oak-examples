import cv2
import numpy as np

CELL_MM = 50.0
MIN_POINTS_PER_CELL = 3
GRID_SPACING_MM = 100.0
LINE_STEP_MM = 10.0
MIN_EDGE_DISTANCE_MM = 30.0


def build_plane_grid(
    surface_points: np.ndarray,
    plane_eq: np.ndarray,
) -> np.ndarray | None:
    """Returns 3D grid points that outline the surface points on the given plane."""
    normal = _unit_normal(plane_eq)
    u, v = _in_plane_axes(normal)
    footprint = _surface_footprint(np.column_stack([surface_points @ u, surface_points @ v]))
    if footprint is None:
        return None

    # 2D grid on the plane then lifted to 3D
    uv = np.concatenate([_grid_lines(footprint), _outline(footprint)])
    origin = -_normalized_plane_offset(plane_eq) * normal
    return (origin + uv[:, :1] * u + uv[:, 1:] * v).astype(np.float32)


def move_plane_grid(
    points: np.ndarray,
    from_plane: np.ndarray,
    to_plane: np.ndarray
) -> np.ndarray:
    """Moves grid points from from_plane onto to_plane along the normal.

    Both planes must share the same normal, as a plane and its distance-offset
    copy do; only their distance from the camera differs.
    """
    shift = _normalized_plane_offset(from_plane) - _normalized_plane_offset(to_plane)
    return (points + shift * _unit_normal(from_plane)).astype(np.float32)


def _unit_normal(plane_eq: np.ndarray) -> np.ndarray:
    normal = np.asarray(plane_eq[:3], dtype=np.float64)
    return normal / np.linalg.norm(normal)


def _normalized_plane_offset(plane_eq: np.ndarray) -> float:
    """The plane's d for a unit-length normal."""
    return float(plane_eq[3]) / float(np.linalg.norm(plane_eq[:3]))


def _in_plane_axes(normal: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    ref = np.array([0.0, 0.0, 1.0]) if abs(normal[2]) < 0.95 else np.array([0.0, 1.0, 0.0])
    u = np.cross(normal, ref)
    u /= np.linalg.norm(u)
    return u, np.cross(normal, u)


def _surface_footprint(uv: np.ndarray) -> np.ndarray | None:
    """Outline of the surface as a convex polygon (H, 2) in plane coordinates."""
    if uv.shape[0] == 0:
        return None

    cells = np.floor(uv / CELL_MM).astype(np.int64)
    cell_origin = cells.min(axis=0)
    cells -= cell_origin
    cols, rows = cells.max(axis=0) + 1
    counts = np.zeros((rows, cols), dtype=np.int32)
    np.add.at(counts, (cells[:, 1], cells[:, 0]), 1)

    occupied = (counts >= MIN_POINTS_PER_CELL).astype(np.uint8)
    label_count, labels, stats, _ = cv2.connectedComponentsWithStats(occupied, connectivity=8)
    if label_count < 2:
        return None
    largest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))

    rows_idx, cols_idx = np.nonzero(labels == largest)
    centers = (np.column_stack([cols_idx, rows_idx]) + cell_origin + 0.5) * CELL_MM
    if centers.shape[0] < 3:
        return None

    hull = cv2.convexHull(centers.astype(np.float32)).reshape(-1, 2)
    return hull.astype(np.float64) if hull.shape[0] >= 3 else None


def _grid_lines(polygon: np.ndarray) -> np.ndarray:
    """Points along grid lines at multiples of the spacing, clipped to the polygon."""
    low, high = polygon.min(axis=0), polygon.max(axis=0)
    lines: list[np.ndarray] = []

    for axis in (0, 1):
        other = 1 - axis
        samples = np.arange(low[other], high[other] + LINE_STEP_MM, LINE_STEP_MM)
        first = np.ceil(low[axis] / GRID_SPACING_MM) * GRID_SPACING_MM
        for position in np.arange(first, high[axis], GRID_SPACING_MM):
            line = np.empty((samples.size, 2))
            line[:, axis] = position
            line[:, other] = samples
            distance = _signed_distance(line, polygon)
            # Skip lines that stay too close to the boundary
            if distance.max() < MIN_EDGE_DISTANCE_MM:
                continue
            lines.append(line[distance >= 0])

    return np.concatenate(lines) if lines else np.empty((0, 2))


def _outline(polygon: np.ndarray) -> np.ndarray:
    """Points along the polygon's edges."""
    parts = []
    for start, end in zip(polygon, np.roll(polygon, -1, axis=0)):
        count = max(2, int(np.ceil(np.linalg.norm(end - start) / LINE_STEP_MM)) + 1)
        parts.append(start + np.linspace(0.0, 1.0, count)[:, None] * (end - start))
    return np.concatenate(parts)


def _signed_distance(points: np.ndarray, polygon: np.ndarray) -> np.ndarray:
    """Distance from each point to the outline: positive inside, negative outside."""
    contour = polygon.astype(np.float32).reshape(-1, 1, 2)
    return np.array(
        [cv2.pointPolygonTest(contour, (float(x), float(y)), True) for x, y in points]
    )
