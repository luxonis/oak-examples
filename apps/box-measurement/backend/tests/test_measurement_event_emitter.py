"""Application completion policy through public observations and event messages."""

import unittest
from datetime import timedelta

import depthai as dai

from depthai_pipeline.message.measurement_event import (
    MeasurementEventKind,
    MeasurementEventTrigger,
    MeasurementUpdate,
)
from depthai_pipeline.node.measurement_event_emitter import MeasurementEventEmitter
from solutions_sdk.box_measurement import (
    BoxDimensions,
    BoxMeasurementResult,
    BoxMeasurements,
    MeasurementStatus,
)

SUCCESS = MeasurementEventKind.SUCCESS
INCOMPLETE = MeasurementEventKind.INCOMPLETE
FAILED_LOW_COVERAGE = MeasurementEventKind.FAILED_LOW_COVERAGE
UPDATE = MeasurementUpdate
DIMENSIONS = BoxDimensions(length_mm=200, width_mm=100, height_mm=50)


def observation(status=MeasurementStatus.MEASURED, dimensions=DIMENSIONS, track_id=7):
    bbox = dai.RotatedRect()
    bbox.center = dai.Point2f(0.5, 0.5)
    bbox.size = dai.Size2f(0.4, 0.4)
    return BoxMeasurementResult(
        track_id=track_id,
        bounding_box=bbox,
        confidence=0.8,
        track_status=dai.Tracklet.TrackingStatus.TRACKED,
        measurement_status=status,
        dimensions=dimensions,
    )


class ObservationSource(dai.node.HostNode):
    def process(self, observations):
        self.out.send(observations)


class EmitterPipeline:
    """Events carry their source frame's sequence number, so the exact frame
    each event fires on is asserted after the fact; a later known event proves
    nothing else fired in between."""

    def __init__(self):
        self.pipeline = dai.Pipeline(False)
        source = self.pipeline.create(ObservationSource)
        source.inputs["observations"].setBlocking(True)
        self.input = source.inputs["observations"].createInputQueue(blocking=True)
        emitter = self.pipeline.create(MeasurementEventEmitter).build(source.out)
        emitter.inputs["measurements"].setBlocking(True)
        self._events = emitter.out_events.createOutputQueue(maxSize=100, blocking=True)
        self.pipeline.start()
        self.sequence = 0

    def send(self, items, frames=1):
        for _ in range(frames):
            self.sequence += 1
            self.input.send(
                BoxMeasurements(
                    items,
                    timestamp=timedelta(seconds=self.sequence),
                    timestamp_device=timedelta(seconds=self.sequence + 10),
                    sequence_num=self.sequence,
                )
            )

    def events(self, count):
        received = []
        for _ in range(count):
            event = self._events.get(timedelta(seconds=5))
            if event is None:
                raise AssertionError(f"Expected {count} events, got {received}")
            received.append(event)
        return received

    def close(self):
        self.pipeline.stop()
        self.pipeline.wait()


def event_timeline(events):
    """(event kind or UPDATE, track id, source sequence number) per event."""
    return [
        (
            event.kind if isinstance(event, MeasurementEventTrigger) else type(event),
            event.track_id,
            event.getSequenceNum(),
        )
        for event in events
    ]


class MeasurementEventEmitterTests(unittest.TestCase):
    def setUp(self):
        self.flow = EmitterPipeline()
        self.addCleanup(self.flow.close)

    def test_success_starts_once_after_thirty_measured_received_frames(self):
        self.flow.send([observation()], frames=40)
        self.flow.send([], frames=30)
        events = self.flow.events(2)
        self.assertEqual(event_timeline(events), [(SUCCESS, 7, 30), (UPDATE, 7, 70)])
        self.assertEqual(events[0].volume_mm3, 1_000_000)
        self.assertEqual(events[0].getTimestamp(), timedelta(seconds=30))
        self.assertEqual(events[0].getTimestampDevice(), timedelta(seconds=40))

    def test_completion_uses_last_aggregate_after_thirty_absent_frames(self):
        self.flow.send([observation()], frames=30)
        self.flow.send([observation(dimensions=BoxDimensions(length_mm=240, width_mm=120, height_mm=60))])
        self.flow.send([observation(status=MeasurementStatus.FAILED, dimensions=None)])
        self.flow.send([], frames=30)
        self.flow.send([observation(track_id=8)], frames=30)
        events = self.flow.events(3)
        self.assertEqual(
            event_timeline(events),
            [(SUCCESS, 7, 30), (UPDATE, 7, 62), (SUCCESS, 8, 92)],
        )
        self.assertIsInstance(events[1], MeasurementUpdate)
        self.assertEqual(
            (events[1].length_mm, events[1].width_mm, events[1].height_mm), (240, 120, 60)
        )
        self.assertEqual(events[1].volume_mm3, 1_728_000)

    def test_eligibility_classifies_incomplete_failed_and_ignores_short_tracks(self):
        for index in range(30):
            self.flow.send(
                [
                    observation(
                        status=MeasurementStatus.MEASURED
                        if index == 0
                        else MeasurementStatus.FAILED,
                        track_id=1,
                    ),
                    observation(
                        status=MeasurementStatus.FAILED, dimensions=None, track_id=2
                    ),
                    observation(
                        status=MeasurementStatus.FAILED
                        if index < 29
                        else MeasurementStatus.INELIGIBLE,
                        dimensions=None,
                        track_id=3,
                    ),
                ]
            )
        self.flow.send([], frames=30)
        self.flow.send([observation(track_id=9)], frames=30)
        self.assertEqual(
            event_timeline(self.flow.events(3)),
            [(INCOMPLETE, 1, 60), (FAILED_LOW_COVERAGE, 2, 60), (SUCCESS, 9, 90)],
        )

    def test_reappearance_resets_absence_and_preserves_received_success_count(self):
        self.flow.send([observation()], frames=20)
        self.flow.send([], frames=29)
        self.flow.send([observation()], frames=10)
        self.flow.send([], frames=30)
        self.flow.send([observation()], frames=30)
        self.assertEqual(
            event_timeline(self.flow.events(3)),
            [(SUCCESS, 7, 59), (UPDATE, 7, 89), (SUCCESS, 7, 119)],
        )
