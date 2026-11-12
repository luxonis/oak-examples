"""Application-local events preserve storage policy at the existing events API."""

import tempfile
import time
import unittest
from contextlib import ExitStack
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import depthai as dai
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from test_measurement_event_emitter import ObservationSource

from api import events as events_api
from database.models.base import Base
from depthai_pipeline.message.measurement_event import (
    MeasurementEventKind,
    MeasurementEventTrigger,
    MeasurementUpdate,
)
from depthai_pipeline.node import measurement_event_saver as saver_module


class MeasurementSavingTests(unittest.TestCase):
    def test_failed_saving_setting_and_final_update_reach_events_api(self):
        for save_failed in (False, True):
            with (
                self.subTest(save_failed=save_failed),
                tempfile.TemporaryDirectory() as directory,
                ExitStack() as stack,
            ):
                engine = create_engine(
                    "sqlite:///" + str(Path(directory) / "events.sqlite"),
                    connect_args={"check_same_thread": False},
                )
                self.addCleanup(engine.dispose)
                Base.metadata.create_all(engine)
                sessions = sessionmaker(bind=engine, expire_on_commit=False)
                stack.enter_context(patch.object(saver_module, "DbSession", sessions))
                stack.enter_context(patch.object(events_api, "DbSession", sessions))
                stack.enter_context(
                    patch.object(
                        saver_module, "EVENT_FILES_DIR", Path(directory) / "files"
                    )
                )
                pipeline = dai.Pipeline(False)
                triggers, jpeg, h264 = [
                    pipeline.create(ObservationSource) for _ in range(3)
                ]
                trigger_input, jpeg_input, h264_input = [
                    node.inputs["observations"].createInputQueue()
                    for node in (triggers, jpeg, h264)
                ]
                pipeline.create(saver_module.MeasurementEventSaver).build(
                    triggers.out,
                    jpeg.out,
                    h264.out,
                    fps=10,
                    save_failed_events=save_failed,
                    pre_trigger_duration_seconds=0,
                    video_duration_seconds=2,
                )
                # Also observe the trigger source to know both events reached its output.
                trigger_receipt = triggers.out.createOutputQueue()
                pipeline.start()
                try:
                    for kind, track_id in (
                        (MeasurementEventKind.FAILED_LOW_COVERAGE, 2),
                        (MeasurementEventKind.SUCCESS, 7),
                    ):
                        trigger = MeasurementEventTrigger(
                            kind, track_id, 200, 100, 50, 1_000_000
                        )
                        trigger.setTimestamp(timedelta(seconds=1))
                        trigger_input.send(trigger)
                        trigger_receipt.get()
                    self._send_video(jpeg_input, h264_input, 10)
                    events = self._wait_events(2 if save_failed else 1)
                    self.assertEqual(
                        {event.track_id for event in events},
                        {2, 7} if save_failed else {7},
                    )
                    update = MeasurementUpdate(7, 240, 120, 60, 1_728_000)
                    trigger_input.send(update)
                    trigger_receipt.get()
                    self._send_video(jpeg_input, h264_input, 11)
                    deadline = time.monotonic() + 3
                    while time.monotonic() < deadline:
                        success = next(
                            event
                            for event in self._wait_events(2 if save_failed else 1)
                            if event.track_id == 7
                        )
                        if success.volume_mm3 == 1_728_000:
                            break
                        time.sleep(0.01)
                    self.assertEqual(
                        (
                            success.length_mm,
                            success.width_mm,
                            success.height_mm,
                            success.volume_mm3,
                        ),
                        (240, 120, 60, 1_728_000),
                    )
                finally:
                    pipeline.stop()
                    pipeline.wait()

    @staticmethod
    def _wait_events(count):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            events = events_api.get_events(events_api.GetEventsRequest()).events
            if len(events) == count:
                return events
            time.sleep(0.01)
        raise AssertionError(f"Expected {count} stored events, got {len(events)}")

    @staticmethod
    def _send_video(jpeg_input, h264_input, seconds):
        jpeg = dai.EncodedFrame()
        jpeg.setProfile(dai.EncodedFrame.Profile.JPEG)
        jpeg.setData(b"jpeg-test-thumbnail")
        h264 = dai.EncodedFrame()
        h264.setProfile(dai.EncodedFrame.Profile.AVC)
        # A non-keyframe exercises saving without requiring an encoder in host-only tests.
        h264.setFrameType(dai.EncodedFrame.FrameType.P)
        for frame in (jpeg, h264):
            frame.setTimestamp(timedelta(seconds=seconds))
            frame.setSequenceNum(seconds)
        jpeg_input.send(jpeg)
        h264_input.send(h264)
