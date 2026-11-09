import depthai as dai

from depthai_pipeline.common.message.danger_assessment import DangerAssessment
from depthai_pipeline.common.message.danger_classification import (
    DangerClassification,
    DangerLevel,
    DangerSource,
)
from util.danger_zones import is_at_least_as_severe, max_level


class DangerClassifier(dai.node.ThreadedHostNode):
    """Combine available detector assessments and smooth alert transitions.

    Severity increases immediately. SAFE must persist for a configured number
    of frames before the current alert is cleared.
    """

    _SEGMENTATION_INPUT_NAME = "segmentation_assessment"
    _POINTCLOUD_INPUT_NAME = "pointcloud_assessment"
    _AWARENESS_RESET_DEBOUNCE_FRAMES = 5

    def __init__(self) -> None:
        super().__init__()
        self._sync: dai.node.Sync = self.createSubnode(dai.node.Sync)
        self._sync.setRunOnHost(True)
        self._synced_assessments_input = self.createInput(name="synced_assessments")
        self._out = self.createOutput(name="out")
        self._has_pointcloud_input = False
        self._deescalation_frames = 10
        self._awareness_escalation_frames: float | None = None
        self._state = DangerLevel.SAFE
        self._deescalation_count = 0
        self._awareness_escalation_count = 0
        self._awareness_reset_count = 0

    @property
    def out(self) -> dai.Node.Output:
        return self._out

    def build(
        self,
        segmentation_assessment: dai.Node.Output,
        pointcloud_assessment: dai.Node.Output | None = None,
        deescalation_frames: int = 10,
        awareness_escalation_frames: float | None = None,
    ) -> "DangerClassifier":
        """Connect assessment sources and configure temporal thresholds.

        Args:
            segmentation_assessment: Person segmentation assessment stream.
            pointcloud_assessment: Optional obstacle assessment stream.
            deescalation_frames: Consecutive SAFE frames needed to clear an alert.
            awareness_escalation_frames: WARNING frames before promoting to DANGER;
                None disables this promotion.

        Returns:
            This configured node.
        """
        self._has_pointcloud_input = pointcloud_assessment is not None
        segmentation_assessment.link(self._sync.inputs[self._SEGMENTATION_INPUT_NAME])
        if pointcloud_assessment is not None:
            pointcloud_assessment.link(self._sync.inputs[self._POINTCLOUD_INPUT_NAME])
        self._sync.out.link(self._synced_assessments_input)
        self._deescalation_frames = deescalation_frames
        self._awareness_escalation_frames = awareness_escalation_frames
        self._state = DangerLevel.SAFE
        self._deescalation_count = 0
        self._awareness_escalation_count = 0
        self._awareness_reset_count = 0
        return self

    def run(self) -> None:
        while self.isRunning():
            try:
                synced_assessments = self._synced_assessments_input.get()
                assert isinstance(synced_assessments, dai.MessageGroup)
                self._process_synced_assessments(synced_assessments)
            except dai.MessageQueue.QueueException:
                break

    def _process_synced_assessments(
        self,
        synced_assessments: dai.MessageGroup,
    ) -> None:
        segmentation_assessment = synced_assessments[self._SEGMENTATION_INPUT_NAME]
        assert isinstance(segmentation_assessment, DangerAssessment)

        pointcloud_assessment: DangerAssessment | None = None
        if self._has_pointcloud_input:
            pointcloud_assessment_msg = synced_assessments[self._POINTCLOUD_INPUT_NAME]
            assert isinstance(pointcloud_assessment_msg, DangerAssessment)
            pointcloud_assessment = pointcloud_assessment_msg

        self._process_assessments(
            segmentation_assessment=segmentation_assessment,
            pointcloud_assessment=pointcloud_assessment,
        )

    def _process_assessments(
        self,
        segmentation_assessment: DangerAssessment,
        pointcloud_assessment: DangerAssessment | None = None,
    ) -> None:
        if not self._has_pointcloud_input:
            pointcloud_assessment = None

        assessments = [segmentation_assessment]
        if pointcloud_assessment is not None:
            assessments.append(pointcloud_assessment)

        raw_level, active_sources = self._get_raw_level(*assessments)
        self._advance_state(raw_level)
        classification = DangerClassification()
        classification.level = self._state
        classification.danger_detections = segmentation_assessment.danger_detections
        classification.active_sources = active_sources
        classification.setSequenceNum(segmentation_assessment.getSequenceNum())
        classification.setTimestamp(segmentation_assessment.getTimestamp())
        classification.setTimestampDevice(segmentation_assessment.getTimestampDevice())
        self._out.send(classification)

    def _get_raw_level(
        self,
        *assessments: DangerAssessment,
    ) -> tuple[DangerLevel, list[DangerSource]]:
        available_assessments = [
            assessment for assessment in assessments if assessment.available
        ]
        if not available_assessments:
            return DangerLevel.SAFE, []

        raw_level = max_level(assessment.level for assessment in available_assessments)
        if raw_level == DangerLevel.SAFE:
            return raw_level, []

        active_sources = [
            assessment.source
            for assessment in available_assessments
            if assessment.level == raw_level
        ]
        return raw_level, active_sources

    def _advance_state(self, raw_level: DangerLevel) -> None:
        """Advance the alert state using SAFE debounce and WARNING awareness."""
        if raw_level == DangerLevel.SAFE:
            self._deescalation_count += 1
            self._awareness_reset_count += 1
            if (
                self._awareness_escalation_frames is not None
                and self._awareness_reset_count >= self._AWARENESS_RESET_DEBOUNCE_FRAMES
            ):
                self._awareness_escalation_count = 0
            if self._deescalation_count >= self._deescalation_frames:
                self._awareness_escalation_count = 0
                self._awareness_reset_count = 0
                self._state = raw_level
            return

        self._deescalation_count = 0
        self._awareness_reset_count = 0

        if is_at_least_as_severe(raw_level, self._state):
            self._state = raw_level
        if raw_level == DangerLevel.WARNING:
            if self._awareness_escalation_frames is not None:
                if (
                    self._awareness_escalation_count
                    >= self._awareness_escalation_frames
                ):
                    self._state = DangerLevel.DANGER
                else:
                    self._awareness_escalation_count += 1
