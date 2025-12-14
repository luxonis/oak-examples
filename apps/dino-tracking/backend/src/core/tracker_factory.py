import depthai as dai


class TrackerFactory:
    """
    Creates and wires a dai.node.ObjectTracker for heatmap-based detections.
    """

    def __init__(
        self,
        pipeline: dai.Pipeline,
        detections_out: dai.Node.Output,
        video_out: dai.Node.Output,
    ):
        self._pipeline = pipeline
        self._detections_out = detections_out
        self._video_out = video_out

    def build(self) -> dai.node.ObjectTracker:
        tracker = self._pipeline.create(dai.node.ObjectTracker)
        tracker.setTrackerType(
            dai.TrackerType.ZERO_TERM_COLOR_HISTOGRAM
        )
        tracker.setTrackerIdAssignmentPolicy(
            dai.TrackerIdAssignmentPolicy.UNIQUE_ID
        )
        tracker.setDetectionLabelsToTrack([0])

        self._video_out.link(tracker.inputDetectionFrame)
        self._video_out.link(tracker.inputTrackerFrame)
        self._detections_out.link(tracker.inputDetections)

        return tracker
