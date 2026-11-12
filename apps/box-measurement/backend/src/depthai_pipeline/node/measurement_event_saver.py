import logging
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

import av
import depthai as dai

from database.connection import DbSession
from database.models.event import MeasurementEventType
from database.repositories.event_repository import (
    EventRepository,
    MeasurementEventData,
    MeasurementEventFileData,
)
from depthai_pipeline.message.measurement_event import (
    MeasurementEventKind,
    MeasurementEventTrigger,
    MeasurementUpdate,
)
from util.event_files import EVENT_FILES_DIR

logger = logging.getLogger(__name__)


class EncodedVideoFrameBuffer:
    """Rolling buffer of the last N seconds of encoded frames (pre-trigger)."""

    def __init__(self, pre_trigger_duration_seconds: int):
        self._pre_trigger_duration_seconds = pre_trigger_duration_seconds
        self._frames: deque[dai.EncodedFrame] = deque()

    def append(self, encoded_frame: dai.EncodedFrame) -> None:
        self._frames.append(encoded_frame)
        self._trim(encoded_frame.getTimestamp().total_seconds())

    def frames_for_trigger(
        self, trigger_timestamp_seconds: float
    ) -> list[dai.EncodedFrame]:
        start_timestamp = max(
            0.0, trigger_timestamp_seconds - self._pre_trigger_duration_seconds
        )
        return [
            frame
            for frame in self._frames
            if start_timestamp
            <= frame.getTimestamp().total_seconds()
            <= trigger_timestamp_seconds
        ]

    def _trim(self, newest_timestamp_seconds: float) -> None:
        cutoff = newest_timestamp_seconds - self._pre_trigger_duration_seconds
        while (
            len(self._frames) > 1
            and self._frames[0].getTimestamp().total_seconds() < cutoff
        ):
            self._frames.popleft()


class H264VideoRecordingContainer:
    """Collects raw H264 frames for one event and muxes them into an mp4."""

    def __init__(self, filename: str, end_timestamp_seconds: float):
        self._filename = filename
        self._end_timestamp_seconds = end_timestamp_seconds
        self._frames: list[dai.EncodedFrame] = []

    @property
    def filepath(self) -> Path:
        return EVENT_FILES_DIR / self._filename

    @property
    def filename(self) -> str:
        return self._filename

    def is_complete(self, timestamp_seconds: float) -> bool:
        return timestamp_seconds > self._end_timestamp_seconds

    def has_frames(self) -> bool:
        return bool(self._frames)

    def add_frames(self, frames: list[dai.EncodedFrame]) -> None:
        for frame in frames:
            self.add_frame(frame)

    def add_frame(self, frame: dai.EncodedFrame) -> None:
        if frame.getTimestamp().total_seconds() > self._end_timestamp_seconds:
            return

        # A decoder cannot start mid-GOP: drop frames until the first keyframe.
        if not self._frames and frame.getFrameType() != dai.EncodedFrame.FrameType.I:
            return

        self._frames.append(frame)

    def create_video_file(self, fps: int) -> None:
        if not self._frames:
            raise RuntimeError("No frames are available to create a video file")

        try:
            with av.open(self.filepath, "w") as output_container:
                stream = output_container.add_stream("h264", rate=fps)
                stream.time_base = Fraction(1, 1_000_000)
                stream.width = self._frames[0].getWidth()
                stream.height = self._frames[0].getHeight()
                container_start_time = self._frames[0].getTimestamp()

                for h264_encoded_frame in self._frames:
                    data = h264_encoded_frame.getData()
                    packet = av.Packet(data.tobytes())
                    timestamp = (
                        h264_encoded_frame.getTimestamp() - container_start_time
                    ).total_seconds()
                    packet.pts = int(timestamp * 1_000_000)
                    packet.dts = int(timestamp * 1_000_000)
                    assert stream.time_base is not None
                    packet.time_base = stream.time_base
                    packet.stream = stream
                    output_container.mux(packet)
        except Exception:
            self._delete_current_recording()
            raise
        finally:
            self._frames.clear()

    def abort(self) -> None:
        self._frames.clear()
        self._delete_current_recording()

    def _delete_current_recording(self) -> None:
        try:
            self.filepath.unlink(missing_ok=True)
        except Exception:
            logger.exception("Failed to clean up saved event video")


@dataclass
class _ActiveRecording:
    event_data: MeasurementEventData
    container: H264VideoRecordingContainer


class MeasurementEventSaver(dai.node.HostNode):
    """Persists measurement events: thumbnail + video clip on disk, metadata in DB."""

    def build(
        self,
        triggers: dai.Node.Output,
        mjpeg_encoded_frames: dai.Node.Output,
        h264_encoded_frames: dai.Node.Output,
        fps: int,
        save_failed_events: bool = True,
        pre_trigger_duration_seconds: int = 5,
        video_duration_seconds: int = 15,
    ) -> "MeasurementEventSaver":
        self.link_args(mjpeg_encoded_frames, h264_encoded_frames)
        EVENT_FILES_DIR.mkdir(parents=True, exist_ok=True)
        self._trigger_input = self.createInput()
        self._trigger_input.setBlocking(False)
        self._trigger_input.setMaxSize(50)
        triggers.link(self._trigger_input)
        self._fps = fps
        self._save_failed_events = save_failed_events
        self._pre_trigger_duration_seconds = pre_trigger_duration_seconds
        self._video_duration_seconds = video_duration_seconds
        self._frame_buffer = EncodedVideoFrameBuffer(pre_trigger_duration_seconds)
        self._active_recordings: list[_ActiveRecording] = []
        # track_id -> event_id, so a later MeasurementUpdate can patch the row after the measurement was finalized.
        self._success_event_ids: dict[int, int] = {}
        return self

    def process(
        self,
        mjpeg_encoded_frame: dai.Buffer,
        h264_encoded_frame: dai.Buffer,
    ) -> None:
        assert isinstance(mjpeg_encoded_frame, dai.EncodedFrame)
        assert isinstance(h264_encoded_frame, dai.EncodedFrame)

        for message in self._trigger_input.tryGetAll():
            if isinstance(message, MeasurementUpdate):
                self._apply_measurement_update(message)
                continue
            assert isinstance(message, MeasurementEventTrigger)
            self._start_recording(message, mjpeg_encoded_frame)

        frame_timestamp = h264_encoded_frame.getTimestamp().total_seconds()
        still_active: list[_ActiveRecording] = []
        for recording in self._active_recordings:
            recording.container.add_frame(h264_encoded_frame)
            if recording.container.is_complete(frame_timestamp):
                self._finalize_recording(recording)
            else:
                still_active.append(recording)
        self._active_recordings = still_active

        self._frame_buffer.append(h264_encoded_frame)

    def onStop(self) -> None:  # noqa: N802 - DepthAI HostNode lifecycle hook
        for recording in self._active_recordings:
            self._finalize_recording(recording)
        self._active_recordings = []

    def _start_recording(
        self,
        trigger: MeasurementEventTrigger,
        mjpeg_encoded_frame: dai.EncodedFrame,
    ) -> None:
        if (
            trigger.kind != MeasurementEventKind.SUCCESS
            and not self._save_failed_events
        ):
            logger.info(
                "Skipping %s event because saving failed events is disabled",
                trigger.kind.value,
            )
            return

        created_at = datetime.now(timezone.utc)
        event_data = MeasurementEventData(
            created_at=created_at,
            event_type=MeasurementEventType(trigger.kind.value),
            track_id=trigger.track_id,
            length_mm=trigger.length_mm,
            width_mm=trigger.width_mm,
            height_mm=trigger.height_mm,
            volume_mm3=trigger.volume_mm3,
        )
        try:
            image_path = self._save_jpg_image(mjpeg_encoded_frame, created_at)
            event_data.files.append(
                MeasurementEventFileData(name="image", path=image_path)
            )
        except Exception:
            logger.exception("Failed to save event image")

        trigger_timestamp = trigger.getTimestamp().total_seconds()
        container = H264VideoRecordingContainer(
            filename=self._build_filename(created_at, trigger.track_id, "mp4"),
            end_timestamp_seconds=trigger_timestamp
            + (self._video_duration_seconds - self._pre_trigger_duration_seconds),
        )
        container.add_frames(self._frame_buffer.frames_for_trigger(trigger_timestamp))

        logger.info(
            "Started event recording for %s (track %d)",
            trigger.kind.value,
            trigger.track_id,
        )
        self._active_recordings.append(
            _ActiveRecording(event_data=event_data, container=container)
        )

    def _finalize_recording(self, recording: _ActiveRecording) -> None:
        if recording.container.has_frames():
            try:
                recording.container.create_video_file(self._fps)
                recording.event_data.files.append(
                    MeasurementEventFileData(
                        name="video", path=recording.container.filename
                    )
                )
            except Exception:
                logger.exception("Failed to persist event video")

        try:
            with DbSession() as session:
                event_id = EventRepository(session).add(recording.event_data)
            if recording.event_data.event_type == MeasurementEventType.SUCCESS:
                self._remember_success_event(
                    recording.event_data.track_id, event_id
                )
            logger.info(
                "Saved %s event for track %d",
                recording.event_data.event_type.value,
                recording.event_data.track_id,
            )
        except Exception:
            logger.exception("Failed to save measurement event to the database")

    def _remember_success_event(self, track_id: int, event_id: int) -> None:
        self._success_event_ids[track_id] = event_id
        while len(self._success_event_ids) > 100:
            oldest_track_id = next(iter(self._success_event_ids))
            del self._success_event_ids[oldest_track_id]

    def _apply_measurement_update(self, update: MeasurementUpdate) -> None:
        # The track may still be recording (row not yet written): patch the
        # in-flight event data so the final median lands in the initial insert.
        for recording in self._active_recordings:
            if (
                recording.event_data.track_id == update.track_id
                and recording.event_data.event_type == MeasurementEventType.SUCCESS
            ):
                recording.event_data.length_mm = update.length_mm
                recording.event_data.width_mm = update.width_mm
                recording.event_data.height_mm = update.height_mm
                recording.event_data.volume_mm3 = update.volume_mm3
                logger.info(
                    "Applied final median to in-flight event (track %d)",
                    update.track_id,
                )
                return

        event_id = self._success_event_ids.pop(update.track_id, None)
        if event_id is None:
            logger.warning(
                "No stored SUCCESS event found for final median update "
                "(track %d)",
                update.track_id,
            )
            return

        try:
            with DbSession() as session:
                updated = EventRepository(session).update_dimensions(
                    event_id,
                    length_mm=update.length_mm,
                    width_mm=update.width_mm,
                    height_mm=update.height_mm,
                    volume_mm3=update.volume_mm3,
                )
            if updated:
                logger.info(
                    "Updated event %d with final median (track %d)",
                    event_id,
                    update.track_id,
                )
        except Exception:
            logger.exception("Failed to apply final median update")

    def _save_jpg_image(
        self, encoded_frame: dai.EncodedFrame, created_at: datetime
    ) -> str:
        if encoded_frame.getProfile() != dai.EncodedFrame.Profile.JPEG:
            raise ValueError(
                "MeasurementEventSaver expected a JPEG-encoded frame for the thumbnail"
            )

        filename = self._build_filename(created_at, None, "jpg")
        (EVENT_FILES_DIR / filename).write_bytes(bytes(encoded_frame.getData()))
        return filename

    @staticmethod
    def _build_filename(
        created_at: datetime, track_id: int | None, extension: str
    ) -> str:
        timestamp = created_at.strftime("%Y%m%dT%H%M%S%fZ")
        suffix = f"-track{track_id}" if track_id is not None else ""
        return f"event-{timestamp}{suffix}.{extension}"
