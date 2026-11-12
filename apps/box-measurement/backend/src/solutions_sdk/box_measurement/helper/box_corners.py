"""Conversion between axis-aligned box corners and zero-angle RotatedRects."""

import depthai as dai


def rect_from_corners(
    xmin: float, ymin: float, xmax: float, ymax: float
) -> dai.RotatedRect:
    """Return the zero-angle rectangle spanning the given corners."""
    return dai.RotatedRect(
        dai.Point2f((xmin + xmax) / 2, (ymin + ymax) / 2),
        dai.Size2f(xmax - xmin, ymax - ymin),
        0,
    )


def rect_corners(rect: dai.RotatedRect) -> tuple[float, float, float, float]:
    """Return ``(xmin, ymin, xmax, ymax)`` of a zero-angle rectangle."""
    half_width = rect.size.width / 2
    half_height = rect.size.height / 2
    return (
        rect.center.x - half_width,
        rect.center.y - half_height,
        rect.center.x + half_width,
        rect.center.y + half_height,
    )
