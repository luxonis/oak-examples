import depthai as dai
from depthai_nodes.message import BoxMeasurementResult, BoxMeasurements
from depthai_nodes.utils import AnnotationHelper


class BoxOverlay(dai.node.HostNode):
    """Draw the boxes that one view sees, with their ID, status and dimensions."""

    def __init__(self) -> None:
        super().__init__()
        self._view = 0

    def build(self, measurements: dai.Node.Output, view: int) -> "BoxOverlay":
        """Link the measurements and select the view, by its index in BoxMeasurer.build."""
        self.link_args(measurements)
        self._view = view
        return self

    def process(self, measurements: dai.Buffer) -> None:
        assert isinstance(measurements, BoxMeasurements)
        annotations = AnnotationHelper()
        for result in measurements.items:
            for detection in result.detections:
                if detection.view != self._view:
                    continue
                # Normalized to this view's color frame.
                box = detection.bounding_box
                annotations.draw_rotated_rect(
                    (box.center.x, box.center.y),
                    (box.size.width, box.size.height),
                    box.angle,
                    fill_color=None,
                    thickness=3.0,
                )
                xmin, ymin, _, _ = box.getOuterRect()
                annotations.draw_text(
                    format_label(result),
                    (max(0.0, xmin), max(0.0, ymin - 0.01)),
                    color=(1.0, 1.0, 1.0, 1.0),
                    background_color=(0.0, 0.0, 0.0, 0.6),
                    size=20.0,
                )
        message = annotations.build(
            measurements.getTimestamp(), measurements.getSequenceNum()
        )
        message.setBufferMetadataFrom(measurements)
        self.out.send(message)


def format_label(result: BoxMeasurementResult) -> str:
    """Return the box ID, the measurement status and, once measured, the dimensions."""
    text = f"Box {result.box_id} {result.measurement_status.value}"
    size = result.dimensions
    if size is not None:
        text += (
            f"\n{size.length_mm / 10:.1f} x {size.width_mm / 10:.1f}"
            f" x {size.height_mm / 10:.1f} cm"
        )
    return text
