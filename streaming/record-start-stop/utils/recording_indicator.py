import math

import depthai as dai

REC_COLOR = dai.Color(0.86, 0.12, 0.12, 1.0)
IDLE_COLOR = dai.Color(0.45, 0.45, 0.45, 1.0)
ERROR_COLOR = dai.Color(0.95, 0.75, 0.1, 1.0)
TEXT_COLOR = dai.Color(1.0, 1.0, 1.0, 1.0)
TEXT_BACKGROUND = dai.Color(0.0, 0.0, 0.0, 0.55)
# Fraction of the frame width. The matching vertical radius is larger in
# normalized coordinates so the mark is round on a wide preview.
MARKER_RADIUS_X = 0.016
MARKER_SEGMENTS = 32


class RecordingIndicator(dai.node.HostNode):
    """Draws the record-node state on the camera preview."""

    def __init__(self) -> None:
        super().__init__()
        self._record = None
        self._auto = False
        self._aspect = 1.0
        self.output = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.ImgAnnotations, True)
            ]
        )

    def build(
        self,
        frames: dai.Node.Output,
        record: dai.node.RecordVideo,
        auto_record: bool,
        frame_size: tuple[int, int],
    ) -> "RecordingIndicator":
        self.link_args(frames)
        self._record = record
        self._auto = auto_record
        width, height = frame_size
        if width > 0 and height > 0:
            self._aspect = width / height
        return self

    def process(self, frame: dai.Buffer) -> None:
        status = None if self._record is None else self._record.getStatus()
        state = None if status is None else status.state
        if state == dai.RecordStatus.State.STARTED:
            label = "REC"
            color = REC_COLOR
        elif state == dai.RecordStatus.State.ERROR:
            label = "ERROR"
            color = ERROR_COLOR
        else:
            label = "IDLE"
            color = IDLE_COLOR
        if self._auto:
            label = f"{label} auto"

        annotation = dai.ImgAnnotation()
        # CircleAnnotation is always drawn red, and a wide frame stretches it
        # into a tall oval. A filled loop keeps this color and a round shape.
        marker = dai.PointsAnnotation()
        marker.type = dai.PointsAnnotationType.LINE_LOOP
        marker.fillColor = color
        marker.outlineColor = color
        marker.thickness = 1.0
        marker.points = dai.VectorPoint2f(
            _marker_points(0.035, 0.07, MARKER_RADIUS_X, self._aspect)
        )
        annotation.points.append(marker)

        text = dai.TextAnnotation()
        text.position = dai.Point2f(0.06, 0.04)
        text.text = label
        text.fontSize = 14
        text.textColor = TEXT_COLOR
        text.backgroundColor = TEXT_BACKGROUND
        annotation.texts.append(text)

        hint = dai.TextAnnotation()
        hint.position = dai.Point2f(0.06, 0.10)
        hint.text = "r start/stop"
        hint.fontSize = 12
        hint.textColor = TEXT_COLOR
        hint.backgroundColor = TEXT_BACKGROUND
        annotation.texts.append(hint)

        annotations = dai.ImgAnnotations()
        annotations.annotations.append(annotation)
        annotations.setTimestamp(frame.getTimestamp())
        self.output.send(annotations)


def _marker_points(
    center_x: float, center_y: float, radius_x: float, aspect: float
) -> list[dai.Point2f]:
    """Normalized points for a circle on a frame of the given width/height."""
    radius_y = radius_x * aspect
    points = []
    for index in range(MARKER_SEGMENTS):
        angle = (2.0 * math.pi * index) / MARKER_SEGMENTS
        points.append(
            dai.Point2f(
                center_x + radius_x * math.cos(angle),
                center_y + radius_y * math.sin(angle),
            )
        )
    return points
