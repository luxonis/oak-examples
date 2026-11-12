"""Shared drawing of labelled box outlines for visualization messages."""

from datetime import timedelta

import depthai as dai
from depthai_nodes.utils import AnnotationHelper

from solutions_sdk.box_measurement.helper.box_corners import rect_corners


def build_box_annotations(
    boxes: list[tuple[dai.RotatedRect, str]],
    timestamp: timedelta,
    timestamp_device: timedelta,
    sequence_num: int,
) -> dai.ImgAnnotations:
    """Outline each normalized box with its label above the top-left corner."""
    annotations = AnnotationHelper()
    for rect, label in boxes:
        xmin, ymin, xmax, ymax = rect_corners(rect)
        annotations.draw_rectangle(
            (xmin, ymin),
            (xmax, ymax),
            fill_color=None,
            thickness=3.0,
        )
        annotations.draw_text(
            label,
            (xmin, max(0.0, ymin - 0.01)),
            color=(1.0, 1.0, 1.0, 1.0),
            background_color=(0.0, 0.0, 0.0, 0.6),
            size=28.0,
        )
    message = annotations.build(timestamp, sequence_num)
    message.setTimestampDevice(timestamp_device)
    return message
