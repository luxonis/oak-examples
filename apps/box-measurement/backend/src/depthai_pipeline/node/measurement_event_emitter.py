"""Application policy for readiness, completion and recording SDK observations."""

from dataclasses import dataclass

import depthai as dai

from depthai_pipeline.message.measurement_event import (
    MeasurementEventKind,
    MeasurementEventTrigger,
    MeasurementUpdate,
)
from solutions_sdk.box_measurement import (
    BoxDimensions,
    BoxMeasurements,
    MeasurementStatus,
)


@dataclass
class _ObservedTrack:
    eligible: int = 0
    measured: int = 0
    absent: int = 0
    dimensions: BoxDimensions | None = None
    success_reported: bool = False


class MeasurementEventEmitter(dai.node.HostNode):
    """Translate received observations into application-local recording events."""

    READY_AFTER = 30
    MIN_ELIGIBLE_OBSERVATIONS = 30
    COMPLETE_AFTER_ABSENT = 30

    def __init__(self) -> None:
        super().__init__()
        self.out_events = self.createOutput()
        self._tracks: dict[int, _ObservedTrack] = {}

    def build(self, measurements: dai.Node.Output) -> "MeasurementEventEmitter":
        self.link_args(measurements)
        return self

    def process(self, measurements: dai.Buffer) -> None:
        try:
            self._process(measurements)
        except dai.MessageQueue.QueueException:
            return

    def _process(self, measurements: dai.Buffer) -> None:
        assert isinstance(measurements, BoxMeasurements)
        for box in measurements.items:
            track = self._tracks.setdefault(box.track_id, _ObservedTrack())
            track.absent = 0
            if box.dimensions is not None:
                track.dimensions = box.dimensions
            if box.measurement_status in (
                MeasurementStatus.FAILED,
                MeasurementStatus.MEASURED,
            ):
                track.eligible += 1
            if box.measurement_status == MeasurementStatus.MEASURED:
                track.measured += 1
            if track.measured >= self.READY_AFTER and not track.success_reported:
                dimensions = track.dimensions
                assert dimensions is not None
                self._emit(
                    MeasurementEventTrigger(
                        MeasurementEventKind.SUCCESS,
                        box.track_id,
                        dimensions.length_mm,
                        dimensions.width_mm,
                        dimensions.height_mm,
                        dimensions.volume_mm3,
                    ),
                    measurements,
                )
                track.success_reported = True
        present = {box.track_id for box in measurements.items}
        for track_id, track in list(self._tracks.items()):
            if track_id in present:
                continue
            track.absent += 1
            if track.absent < self.COMPLETE_AFTER_ABSENT:
                continue
            if track.success_reported and track.dimensions is not None:
                dimensions = track.dimensions
                self._emit(
                    MeasurementUpdate(
                        track_id,
                        dimensions.length_mm,
                        dimensions.width_mm,
                        dimensions.height_mm,
                        dimensions.volume_mm3,
                    ),
                    measurements,
                )
            elif track.eligible >= self.MIN_ELIGIBLE_OBSERVATIONS:
                kind = (
                    MeasurementEventKind.INCOMPLETE
                    if track.measured
                    else MeasurementEventKind.FAILED_LOW_COVERAGE
                )
                self._emit(MeasurementEventTrigger(kind, track_id), measurements)
            del self._tracks[track_id]

    def _emit(self, event: dai.Buffer, source: BoxMeasurements) -> None:
        event.setTimestamp(source.getTimestamp())
        event.setTimestampDevice(source.getTimestampDevice())
        event.setSequenceNum(source.getSequenceNum())
        self.out_events.send(event)
