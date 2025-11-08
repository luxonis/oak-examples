import depthai as dai
from box import Box


class TrackerFactory:
    def __init__(
        self,
        pipeline: dai.Pipeline,
        detections_bridge: dai.Node.Output,
        video_node: dai.Node.Output,
        config: Box,
    ):
        self._pipeline: dai.Pipeline = pipeline
        self._detections_bridge: dai.Node.Output = detections_bridge
        self._video_node: dai.Node.Output = video_node
        self._config: Box = config

    def build(self) -> dai.node.ObjectTracker:
        tracker = self._pipeline.create(dai.node.ObjectTracker)
        tracker.setTrackerType(dai.TrackerType.SHORT_TERM_IMAGELESS)
        tracker.setTrackerIdAssignmentPolicy(dai.TrackerIdAssignmentPolicy.UNIQUE_ID)
        tracker.setTrackingPerClass(self._config.track_per_class)
        tracker.setTrackletBirthThreshold(self._config.birth_threshold)
        tracker.setTrackletMaxLifespan(self._config.max_lifespan)
        tracker.setOcclusionRatioThreshold(self._config.occlusion_ratio_threshold)
        tracker.setTrackerThreshold(self._config.tracker_threshold)

        self._video_node.link(tracker.inputTrackerFrame)
        self._video_node.link(tracker.inputDetectionFrame)
        self._detections_bridge.link(tracker.inputDetections)

        return tracker
