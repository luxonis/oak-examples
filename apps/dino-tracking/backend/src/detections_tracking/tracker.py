import depthai as dai


class Tracker:
    """
    Creates and wires a dai.node.ObjectTracker for heatmap-based detections.
    """

    def __init__(
        self,
        pipeline: dai.Pipeline,
        detections: dai.Node.Output,
        frame: dai.Node.Output,
    ):
        self._pipeline = pipeline
        self._detections = detections
        self._frame = frame

    def build(self) -> dai.node.ObjectTracker:
        tracker = self._pipeline.create(dai.node.ObjectTracker)
        tracker.setTrackerType(dai.TrackerType.SHORT_TERM_IMAGELESS)
        tracker.setTrackerIdAssignmentPolicy(dai.TrackerIdAssignmentPolicy.UNIQUE_ID)
        tracker.setDetectionLabelsToTrack([0])
        tracker.setTrackletMaxLifespan(30)

        self._frame.link(tracker.inputDetectionFrame)
        self._frame.link(tracker.inputTrackerFrame)
        self._detections.link(tracker.inputDetections)

        return tracker
