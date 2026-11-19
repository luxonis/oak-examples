import cv2
import depthai as dai
import numpy as np

from .measure_object_distance import ObjectDistances


WIDTH = 960
HEIGHT = 720
PLOT_LEFT = 200
PLOT_RIGHT = 760
PLOT_TOP = 88
PLOT_BOTTOM = 648
MAX_X_MM = 7500
MAX_Z_MM = 15000

# BGR colors shared with the light app views and app UI accents.
BACKGROUND = (250, 250, 250)  # #FAFAFA
GRID = (237, 232, 228)  # #E4E8ED
TEXT = (50, 50, 50)  # #323232
PERSON = (198, 84, 112)  # #7054C6
PAIR = (224, 140, 0)  # #008CE0


def project_to_view(x_mm: float, z_mm: float) -> tuple[int, int] | None:
    """Project camera-relative X/Z coordinates into the displayed range."""
    if not (-MAX_X_MM <= x_mm <= MAX_X_MM and 0 <= z_mm <= MAX_Z_MM):
        return None
    x = PLOT_LEFT + round((x_mm + MAX_X_MM) / (2 * MAX_X_MM) * (PLOT_RIGHT - PLOT_LEFT))
    y = PLOT_BOTTOM - round(z_mm / MAX_Z_MM * (PLOT_BOTTOM - PLOT_TOP))
    return x, y


def create_bird_frame() -> np.ndarray:
    frame = np.full((HEIGHT, WIDTH, 3), BACKGROUND, dtype=np.uint8)
    cv2.putText(
        frame,
        "Person positions",
        (36, 48),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.85,
        TEXT,
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        frame, "Z (m)", (80, 102), cv2.FONT_HERSHEY_SIMPLEX, 0.55, TEXT, 1, cv2.LINE_AA
    )

    for x_m in (-5, 0, 5):
        top = project_to_view(x_m * 1000, MAX_Z_MM)
        bottom = project_to_view(x_m * 1000, 0)
        cv2.line(frame, top, bottom, GRID, 1, cv2.LINE_AA)
        label = f"{x_m:+d}" if x_m else "0"
        label_width = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0][0]
        cv2.putText(
            frame,
            label,
            (bottom[0] - label_width // 2, 679),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            TEXT,
            1,
            cv2.LINE_AA,
        )

    for z_m in (0, 5, 10, 15):
        left = project_to_view(-MAX_X_MM, z_m * 1000)
        right = project_to_view(MAX_X_MM, z_m * 1000)
        cv2.line(frame, left, right, GRID, 1, cv2.LINE_AA)
        cv2.putText(
            frame,
            str(z_m),
            (165, left[1] + 5),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            TEXT,
            1,
            cv2.LINE_AA,
        )

    cv2.putText(
        frame, "X (m)", (775, 679), cv2.FONT_HERSHEY_SIMPLEX, 0.55, TEXT, 1, cv2.LINE_AA
    )
    camera = project_to_view(0, 0)
    cv2.circle(frame, camera, 7, TEXT, -1, cv2.LINE_AA)
    cv2.putText(
        frame,
        "camera",
        (camera[0] + 14, camera[1] - 8),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        TEXT,
        1,
        cv2.LINE_AA,
    )
    return frame


def render_bird_frame(distances: ObjectDistances, background: np.ndarray) -> np.ndarray:
    """Show person positions and the closest visible pair's 3D distance."""
    frame = background.copy()
    plotted = {}
    for detection in distances.detections:
        position = project_to_view(
            detection.spatialCoordinates.x, detection.spatialCoordinates.z
        )
        if position is not None:
            plotted[id(detection)] = position

    visible_pairs = (
        pair
        for pair in distances.distances
        if id(pair.detection1) in plotted and id(pair.detection2) in plotted
    )
    closest = min(visible_pairs, key=lambda pair: pair.distance, default=None)
    if closest is not None:
        cv2.line(
            frame,
            plotted[id(closest.detection1)],
            plotted[id(closest.detection2)],
            PAIR,
            2,
            cv2.LINE_AA,
        )
        label = f"Closest pair: {closest.distance / 1000:.1f} m (3D)"
    else:
        label = "Closest pair: --"

    cv2.putText(
        frame, label, (580, 48), cv2.FONT_HERSHEY_SIMPLEX, 0.62, TEXT, 1, cv2.LINE_AA
    )
    for position in plotted.values():
        cv2.circle(frame, position, 10, PERSON, -1, cv2.LINE_AA)
    return frame


class BirdsEyeView(dai.node.HostNode):
    def __init__(self) -> None:
        super().__init__()
        self.output = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.ImgFrame, True)
            ]
        )
        self.background = create_bird_frame()

    def build(self, distances: dai.Node.Output) -> "BirdsEyeView":
        self.link_args(distances)
        return self

    def process(self, distances: dai.Buffer) -> None:
        assert isinstance(distances, ObjectDistances)
        frame = render_bird_frame(distances, self.background)
        output = dai.ImgFrame()
        output.setTimestamp(distances.getTimestamp())
        output.setSequenceNum(distances.getSequenceNum())
        output.setCvFrame(frame, dai.ImgFrame.Type.BGR888p)
        self.output.send(output)
