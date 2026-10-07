import time

import depthai as dai
import numpy as np

from annotations import create_messages
from inference.xmem import HEIGHT, WIDTH


class TrackingPublisher(dai.node.ThreadedHostNode):
    """Publish native overlays and the exact camera frame used for each result."""

    def __init__(self):
        super().__init__()
        self.video = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.ImgFrame, True)
            ]
        )
        self.controller = None

    def run(self):
        """Send matched video and annotations, refreshing overlays on held frames."""
        controller = self.controller
        last = -1
        last_annotation_at = 0

        while self.isRunning() and not controller.stop.is_set():
            with controller.lock:
                tracking = controller.state_data["phase"] in (
                    "tracking",
                    "lost",
                    "catching_up",
                )
                result = controller.result
                packet = controller.latest
                options = dict(controller.state_data["options"])

                if tracking and result and result[4] == controller.epoch:
                    frame, mask, confidence, trail, _ = result
                elif packet and not tracking:
                    frame, mask, confidence, trail = (
                        packet[0],
                        np.zeros((HEIGHT, WIDTH), bool),
                        0,
                        [],
                    )
                else:
                    frame = None

            if frame is None:
                controller.stop.wait(0.005)
                continue
            new_frame = frame.getSequenceNum() != last
            if not new_frame and (
                not tracking or time.monotonic() - last_annotation_at < 0.2
            ):
                controller.stop.wait(0.005)
                continue

            last_annotation_at = time.monotonic()
            dets, segmentation, annotations = create_messages(
                frame, mask, confidence, trail, options
            )
            controller.detections.send(dets)
            controller.segmentation.send(segmentation)
            controller.annotations.send(annotations)

            if new_frame:
                last = frame.getSequenceNum()
                self.video.send(frame)
