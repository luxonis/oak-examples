"""Host-only substitutes for external inference, resize and tracker hardware."""

from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import patch

import depthai as dai
import numpy as np
from device_lookup import patch_device_lookup
from pipeline_io import color_frame, flat_top_cloud, receive

from solutions_sdk.box_measurement import BoxMeasurer


class ColorSource(dai.node.HostNode):
    def process(self, frame):
        self.out.send(frame)


class CloudSource(dai.node.HostNode):
    def process(self, cloud):
        self.out.send(cloud)


class HostResize(dai.node.HostNode):
    def __init__(self):
        super().__init__()
        self.inputImage = self.inputs["frame"]
        self.initialConfig = SimpleNamespace(
            setOutputSize=lambda *a: None, setFrameType=lambda *a: None
        )

    def process(self, frame):
        self.out.send(frame)


class HostInference(dai.node.HostNode):
    threshold = 0.5
    iou = 0.37
    configuration = None

    def __init__(self):
        super().__init__()
        self.config_input = self.createInput()

    def build(self, color, archive):
        self.link_args(color)
        return self

    def getParser(self, kind):
        return SimpleNamespace(
            setConfidenceThreshold=lambda t: setattr(type(self), "threshold", t),
            getIouThreshold=lambda: type(self).iou,
            inputConfig=self.config_input,
        )

    def process(self, frame):
        config = self.config_input.tryGet()
        if config is not None:
            type(self).configuration = config
            type(self).threshold = config.getConfidenceThreshold()
        mode = int(frame.getCvFrame()[0, 0, 0])
        msg = dai.ImgDetections()
        if mode != 0:
            det = dai.ImgDetection()
            det.xmin, det.ymin, det.xmax, det.ymax = (0.2, 0.2, 0.8, 0.8)
            if mode == 2:
                det.xmin = 0.01
            elif mode in (5, 6):
                # Area just above (5) or just below (6) half of the frame.
                det.xmin, det.ymin, det.xmax = (0.1, 0.1, 0.9)
                det.ymax = 0.7255 if mode == 5 else 0.7245
            det.confidence = 0.8
            msg.detections = [det]
            mask = np.full((24, 32), 255, dtype=np.uint8)
            if mode == 4:
                mask = np.full((96, 128), 255, dtype=np.uint8)
                mask[47, 63] = 0
            elif mode != 3:
                mask[5:19, 7:25] = 0
            mask_frame = dai.ImgFrame()
            mask_frame.setCvFrame(mask, dai.ImgFrame.Type.GRAY8)
            msg.setSegmentationMask(mask_frame)
        msg.setTimestamp(frame.getTimestamp())
        msg.setTimestampDevice(frame.getTimestampDevice())
        msg.setSequenceNum(frame.getSequenceNum())
        self.out.send(msg)


class HostTracker(dai.node.HostNode):
    def __init__(self):
        super().__init__()
        self.inputDetections = self.inputs["detections"]
        self.inputTrackerFrame = self.createInput()

    def setTrackerType(self, value):
        pass

    def setTrackerIdAssignmentPolicy(self, value):
        pass

    def process(self, detections):
        while self.inputTrackerFrame.tryGet() is not None:
            pass
        msg = dai.Tracklets()
        tracks = []
        for det in detections.detections:
            track = dai.Tracklet()
            track.id = 7
            track.status = dai.Tracklet.TrackingStatus.TRACKED
            track.roi = dai.Rect(
                dai.Point2f(det.xmin, det.ymin), dai.Point2f(det.xmax, det.ymax)
            )
            tracks.append(track)
        msg.tracklets = tracks
        msg.setTimestamp(detections.getTimestamp())
        msg.setTimestampDevice(detections.getTimestampDevice())
        msg.setSequenceNum(detections.getSequenceNum())
        self.out.send(msg)


def patch_detector_hardware(
    stack: ExitStack,
    platform=dai.Platform.RVC4,
    inference=HostInference,
    tracker=HostTracker,
) -> None:
    """Replace BoxDetector's device, model, resize, NN and tracker for the host."""
    import solutions_sdk.box_measurement.node.detection.box_detector as module

    patch_device_lookup(stack, platform)
    stack.enter_context(patch.object(dai, "getModelFromZoo", return_value="model"))
    stack.enter_context(
        patch.object(
            dai,
            "NNArchive",
            return_value=SimpleNamespace(getInputSize=lambda: (32, 24)),
        )
    )
    stack.enter_context(patch.object(dai.node, "ImageManip", HostResize))
    stack.enter_context(patch.object(dai.node, "ObjectTracker", tracker))
    stack.enter_context(patch.object(module, "ParsingNeuralNetwork", inference))


class MeasurementPipeline:
    def __init__(self, plane=None, blocking=False, max_size=8, with_emitter=False):
        self.stack = ExitStack()
        patch_detector_hardware(self.stack)
        self.pipeline = dai.Pipeline(False)
        colors = self.pipeline.create(ColorSource)
        clouds = self.pipeline.create(CloudSource)
        self.color_input = colors.inputs["frame"].createInputQueue()
        self.cloud_input = clouds.inputs["cloud"].createInputQueue()
        self.measurer = self.pipeline.create(BoxMeasurer).build(
            color=colors.out,
            point_cloud=clouds.out,
            point_cloud_size=(64, 48),
            support_plane=plane,
        )
        self.output = self.measurer.out.createOutputQueue(
            maxSize=max_size, blocking=blocking
        )
        self.cloud_output = self.measurer.box_cloud_out.createOutputQueue(
            maxSize=8, blocking=False
        )
        self.events = None
        if with_emitter:
            from depthai_pipeline.node.measurement_event_emitter import (
                MeasurementEventEmitter,
            )

            emitter = self.pipeline.create(MeasurementEventEmitter).build(
                self.measurer.out
            )
            self.events = emitter.out_events.createOutputQueue(
                maxSize=100, blocking=False
            )
        self.seq = 0
        self.pipeline.start()

    def send(self, height=100, mode=1, depth=True, coverage=1, color_size=(64, 48)):
        self.seq += 1
        cloud = flat_top_cloud(self.seq, (64, 48), height, depth, coverage)
        self.color_input.send(color_frame(self.seq, mode, color_size))
        self.cloud_input.send(cloud)
        return cloud

    def receive(self):
        return receive(self.output)

    def close(self):
        self.pipeline.stop()
        self.pipeline.wait()
        self.stack.close()
