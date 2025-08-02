import cv2
import depthai as dai
import numpy as np
import math

MAX_X = 5000  # mm
MAX_Z = 15000


class BirdsEyeView(dai.node.HostNode):
    def __init__(self) -> None:
        super().__init__()

        self.output = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.ImgFrame, True)
            ]
        )
        self.frame = create_bird_frame()

    def build(self, detections: dai.Node.Output) -> "BirdsEyeView":
        self.link_args(detections)
        return self

    def process(self, tracklets: dai.Tracklets) -> None:
        frame = self.frame.copy()

        for tracklet in tracklets.tracklets:
            x = tracklet.spatialCoordinates.x
            z = tracklet.spatialCoordinates.z

            # check if float is nan
            if math.isnan(x) or math.isnan(z):
                continue

            y = (
                frame.shape[0]
                - int(min(z / (MAX_Z - 10000) * frame.shape[0], frame.shape[0]))
                - 20
            )
            x = int(-x / MAX_X * frame.shape[1] + frame.shape[1] / 2)
            cv2.circle(frame, (x, y), 2, (0, 255, 0), thickness=5, lineType=8, shift=0)

        output = dai.ImgFrame()
        output.setTimestamp(tracklets.getTimestamp())
        output.setCvFrame(frame, dai.ImgFrame.Type.BGR888i)
        self.output.send(output)


def create_bird_frame():
    fov = 68.3
    frame = np.zeros((300, 100, 3), np.uint8)
    cv2.rectangle(frame, (0, 283), (frame.shape[1], frame.shape[0]), (70, 70, 70), -1)

    alpha = (180 - fov) / 2
    center = int(frame.shape[1] / 2)
    max_p = frame.shape[0] - int(math.tan(math.radians(alpha)) * center)
    fov_cnt = np.array(
        [
            (0, frame.shape[0]),
            (frame.shape[1], frame.shape[0]),
            (frame.shape[1], max_p),
            (center, frame.shape[0]),
            (0, max_p),
            (0, frame.shape[0]),
        ]
    )
    cv2.fillPoly(frame, [fov_cnt], color=(70, 70, 70))

    return frame
