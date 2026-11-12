"""Host-only BoxDetector pipeline with scriptable inference and tracker stand-ins."""

from contextlib import ExitStack

import depthai as dai
import numpy as np
from box_measurement_harness import (
    ColorSource,
    HostInference,
    HostTracker,
)
from box_measurement_harness import patch_detector_hardware as patch_hardware
from pipeline_io import color_frame, receive

from solutions_sdk.box_measurement import BoxDetector

# Scripted frames, keyed by the color frame's mode value (its first pixel).
# Inference: list of ((xmin, ymin, xmax, ymax), confidence) and a label mask.
SCRIPTED_DETECTIONS: dict[int, tuple[list, np.ndarray]] = {}
# Tracker: list of (track_id, status, (xmin, ymin, xmax, ymax)).
SCRIPTED_TRACKS: dict[int, list] = {}


class ScriptedInference(HostInference):
    def process(self, frame):
        mode = int(frame.getCvFrame()[0, 0, 0])
        if mode not in SCRIPTED_DETECTIONS:
            super().process(frame)
            return
        config = self.config_input.tryGet()
        if config is not None:
            type(self).configuration = config
            type(self).threshold = config.getConfidenceThreshold()
        boxes, mask = SCRIPTED_DETECTIONS[mode]
        msg = dai.ImgDetections()
        dets = []
        for (xmin, ymin, xmax, ymax), confidence in boxes:
            det = dai.ImgDetection()
            det.xmin, det.ymin, det.xmax, det.ymax = xmin, ymin, xmax, ymax
            det.confidence = confidence
            dets.append(det)
        msg.detections = dets
        mask_frame = dai.ImgFrame()
        mask_frame.setCvFrame(mask, dai.ImgFrame.Type.GRAY8)
        msg.setSegmentationMask(mask_frame)
        msg.setTimestamp(frame.getTimestamp())
        msg.setTimestampDevice(frame.getTimestampDevice())
        msg.setSequenceNum(frame.getSequenceNum())
        self.out.send(msg)


class ScriptedTracker(HostTracker):
    def process(self, detections):
        # The tracker frame is the color stream; read its mode for the script.
        frame = self.inputTrackerFrame.get()
        mode = int(frame.getCvFrame()[0, 0, 0])
        if mode not in SCRIPTED_TRACKS:
            while self.inputTrackerFrame.tryGet() is not None:
                pass
            HostTracker.process(self, detections)
            return
        msg = dai.Tracklets()
        tracks = []
        for track_id, status, (xmin, ymin, xmax, ymax) in SCRIPTED_TRACKS[mode]:
            track = dai.Tracklet()
            track.id = track_id
            track.status = status
            track.roi = dai.Rect(dai.Point2f(xmin, ymin), dai.Point2f(xmax, ymax))
            tracks.append(track)
        msg.tracklets = tracks
        msg.setTimestamp(detections.getTimestamp())
        msg.setTimestampDevice(detections.getTimestampDevice())
        msg.setSequenceNum(detections.getSequenceNum())
        self.out.send(msg)


def patch_detector_hardware(stack: ExitStack, platform=dai.Platform.RVC4) -> None:
    patch_hardware(
        stack, platform, inference=ScriptedInference, tracker=ScriptedTracker
    )


class DetectorPipeline:
    def __init__(self, **build_args):
        self.stack = ExitStack()
        patch_detector_hardware(self.stack)
        self.pipeline = dai.Pipeline(False)
        colors = self.pipeline.create(ColorSource)
        self.color_input = colors.inputs["frame"].createInputQueue()
        try:
            self.detector = self.pipeline.create(BoxDetector).build(
                colors.out, **build_args
            )
        except Exception:
            self.stack.close()
            raise
        self.output = self.detector.out.createOutputQueue(maxSize=8, blocking=False)
        self.seq = 0
        self.pipeline.start()

    def send(self, mode=1, color_size=(64, 48)):
        self.seq += 1
        frame = color_frame(self.seq, mode, color_size)
        self.color_input.send(frame)
        return frame

    def receive(self):
        return receive(self.output)

    def close(self):
        self.pipeline.stop()
        self.pipeline.wait()
        self.stack.close()
