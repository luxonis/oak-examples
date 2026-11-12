"""Tracked box detections from a color stream, with an internally owned model."""

import math
from numbers import Real

import depthai as dai
from depthai_nodes.node import BaseThreadedHostNode, ParsingNeuralNetwork

from solutions_sdk.box_measurement.node.detection.box_detection_assembler import (
    BoxDetectionAssembler,
)

MODEL = "luxonis/box-instance-segmentation:512x320"


def _validate_threshold(threshold: float) -> None:
    if isinstance(threshold, bool) or not isinstance(threshold, Real):
        raise TypeError("Confidence threshold must be a real number")
    if not math.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError("Confidence threshold must be finite and between zero and one")


class BoxDetector(BaseThreadedHostNode):
    """Detect, segment, and track boxes in a color stream.

    ``out`` emits one ``BoxDetections`` per processed frame: a box detection for
    every tracked box with a current, non-empty segmentation, carrying the
    frame's timestamps and sequence number.
    """

    def __init__(self) -> None:
        try:
            super().__init__()
        except AttributeError:
            # The depthai-nodes base reads the default device's platform.
            if self.getParentPipeline().getDefaultDevice() is not None:
                raise
            raise ValueError("BoxDetector currently requires an RVC4 device") from None
        self._iou_threshold = 0.5
        self._config_queue: dai.InputQueue | None = None
        self._assembler = self.createSubnode(BoxDetectionAssembler)

    def build(
        self, color: dai.Node.Output, confidence_threshold: float = 0.5
    ) -> "BoxDetector":
        if self._config_queue is not None:
            raise RuntimeError("BoxDetector is already built")
        _validate_threshold(confidence_threshold)
        if self._platform != dai.Platform.RVC4:
            raise ValueError("BoxDetector currently requires an RVC4 device")
        description = dai.NNModelDescription(MODEL, platform=self._platform.name)
        archive = dai.NNArchive(dai.getModelFromZoo(description))
        size = archive.getInputSize()
        if size is None:
            raise ValueError("NNArchive input size is None")
        resize = self.createSubnode(dai.node.ImageManip)
        resize.initialConfig.setOutputSize(
            *size, dai.ImageManipConfig.ResizeMode.STRETCH
        )
        resize.initialConfig.setFrameType(dai.ImgFrame.Type.BGR888i)
        color.link(resize.inputImage)
        nn = self.createSubnode(ParsingNeuralNetwork).build(resize.out, archive)
        parser = nn.getParser(dai.node.DetectionParser)
        parser.setConfidenceThreshold(confidence_threshold)
        self._iou_threshold = parser.getIouThreshold()
        self._config_queue = parser.inputConfig.createInputQueue()
        tracker = self.createSubnode(dai.node.ObjectTracker)
        tracker.setTrackerType(dai.TrackerType.SHORT_TERM_IMAGELESS)
        tracker.setTrackerIdAssignmentPolicy(dai.TrackerIdAssignmentPolicy.UNIQUE_ID)
        nn.out.link(tracker.inputDetections)
        color.link(tracker.inputTrackerFrame)
        self._assembler.build(tracker.out, nn.out, size)
        return self

    @property
    def out(self) -> dai.Node.Output:
        return self._assembler.out

    def setConfidenceThreshold(self, threshold: float) -> None:
        """Change the detection confidence threshold live; IoU is kept.

        The initial threshold is a ``build`` argument; calling this before
        ``build`` raises ``RuntimeError``.
        """
        if self._config_queue is None:
            raise RuntimeError("BoxDetector is not built")
        _validate_threshold(threshold)
        config = dai.DetectionParserConfig()
        config.setConfidenceThreshold(threshold)
        config.setIouThreshold(self._iou_threshold)
        self._config_queue.send(config)

    def run(self) -> None:
        return
