from typing import List, Optional
import depthai as dai


class PeopleTrackingNode(dai.node.ThreadedHostNode):
    """
    High-level node for people detection + tracking.

    Internal block:
        image_source
          -> ImageManip (resize to NN input resolution)
          -> DetectionNetwork (people detector)
          -> ObjectTracker (track people across frames)

    Exposes:
      - out: tracklets stream (ObjectTracker.out)
    """

    def __init__(
        self,
        labels_to_track: Optional[List[int]] = None,
        det_conf_threshold: float = 0.65,
        tracker_threshold: float = 0.5,
        tracklet_lifespan: int = 15,
        tracker_type: dai.TrackerType = dai.TrackerType.SHORT_TERM_IMAGELESS,
        id_assignment: dai.TrackerIdAssignmentPolicy = dai.TrackerIdAssignmentPolicy.UNIQUE_ID,
    ) -> None:
        """
        @param labels_to_track: Detection labels to track (default [0] = person).
        @param det_conf_threshold: Detection confidence threshold.
        @param tracker_threshold: Tracker confidence threshold.
        @param tracklet_lifespan: Max tracklet lifespan.
        @param tracker_type: Tracking algorithm type.
        @param id_assignment: ID assignment policy for tracklets.
        """
        super().__init__()

        self._labels_to_track = labels_to_track if labels_to_track is not None else [0]
        self._det_conf_threshold = det_conf_threshold
        self._tracker_threshold = tracker_threshold
        self._tracklet_lifespan = tracklet_lifespan
        self._tracker_type = tracker_type
        self._id_assignment = id_assignment

        self._img_manip: dai.node.ImageManip = self.createSubnode(dai.node.ImageManip)
        self._detector: dai.node.DetectionNetwork = self.createSubnode(
            dai.node.DetectionNetwork
        )
        self._tracker: dai.node.ObjectTracker = self.createSubnode(
            dai.node.ObjectTracker
        )

        self.out: dai.Node.Output = self._tracker.out

    def build(
        self,
        image_source: dai.Node.Output,
        archive: dai.NNArchive,
        fps: int,
    ) -> "PeopleTrackingNode":
        """
        @param image_source: Source RGB frames.
        @param archive: NN archive providing the detection model and input resolution.
        @param fps: Camera FPS.
        """
        model_w = archive.getInputWidth()
        model_h = archive.getInputHeight()

        self._img_manip.initialConfig.setOutputSize(model_w, model_h)
        self._img_manip.initialConfig.setReusePreviousImage(False)
        self._img_manip.inputImage.setBlocking(True)
        image_source.link(self._img_manip.inputImage)

        self._detector.build(self._img_manip.out, archive, fps)
        self._detector.setConfidenceThreshold(self._det_conf_threshold)

        self._tracker.setDetectionLabelsToTrack(self._labels_to_track)
        self._tracker.setTrackerThreshold(self._tracker_threshold)
        self._tracker.setTrackletMaxLifespan(self._tracklet_lifespan)
        self._tracker.setTrackerType(self._tracker_type)
        self._tracker.setTrackerIdAssignmentPolicy(self._id_assignment)

        self._detector.out.link(self._tracker.inputDetections)
        self._detector.passthrough.link(self._tracker.inputTrackerFrame)
        self._detector.passthrough.link(self._tracker.inputDetectionFrame)

        return self

    def run(self) -> None:
        # High-level node: no host-side processing, everything runs in subnodes.
        pass
