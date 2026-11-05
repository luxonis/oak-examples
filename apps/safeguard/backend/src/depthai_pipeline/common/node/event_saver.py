import logging
from collections import deque
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

import av
import depthai as dai

from events.event_store import (
    DangerTriggerEventData,
    DangerTriggerEventFileData,
    DangerEventType,
    EventStore,
)
from depthai_pipeline.common.message.danger_classification import (
    DangerClassification,
    DangerLevel,
)

logger = logging.getLogger(__name__)


class EncodedVideoFrameBuffer:
    """Keep a sliding window of encoded frames for pre-trigger video."""

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
    """Collect H.264 frames and remux them into one event clip."""

    def __init__(self, filename: str, end_timestamp_seconds: float, files_dir: Path):
        self._filename = filename
        self._end_timestamp_seconds = end_timestamp_seconds
        self._files_dir = files_dir
        self._frames: list[dai.EncodedFrame] = []

    @property
    def filepath(self) -> Path:
        return self._files_dir / self._filename

    @property
    def filename(self) -> str:
        return self._filename

    def has_frames(self) -> bool:
        return bool(self._frames)

    def add_frames(self, frames: list[dai.EncodedFrame]) -> None:
        for frame in frames:
            self.add_frame(frame)

    def add_frame(self, frame: dai.EncodedFrame) -> None:
        """Append an in-range frame, starting the clip at a keyframe."""
        if frame.getTimestamp().total_seconds() > self._end_timestamp_seconds:
            return

        if not self._frames and frame.getFrameType() != dai.EncodedFrame.FrameType.I:
            return

        self._frames.append(frame)

    def create_video_file(self, fps: int) -> None:
        """Write the collected frames to MP4 with timestamps relative to clip start.

        Args:
            fps: Nominal frame rate for the output stream.

        Raises:
            RuntimeError: No usable frames were collected.
        """
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


class EventSaver(dai.node.HostNode):
    """Capture a still and bounded clip when classification leaves SAFE.

    The event remains open until classification returns to SAFE. A WARNING
    event becomes DANGER if that level occurs before it closes.
    """

    def build(
        self,
        classifications: dai.Node.Output,
        mjpeg_encoded_frames: dai.Node.Output,
        h264_encoded_frames: dai.Node.Output,
        event_store: EventStore,
        fps: int,
        save_warning_events: bool = True,
        save_danger_events: bool = True,
        pre_trigger_duration_seconds: int = 60,
        max_video_duration_seconds: int = 120,
    ) -> "EventSaver":
        """Connect synchronized classification and encoded frame streams.

        Args:
            classifications: Temporally smoothed danger classification.
            mjpeg_encoded_frames: JPEG frames used for event stills.
            h264_encoded_frames: H.264 frames used for event clips.
            event_store: Retained event metadata and file directory.
            fps: Nominal video frame rate.
            save_warning_events: Retain completed WARNING events.
            save_danger_events: Retain completed DANGER events.
            pre_trigger_duration_seconds: Video retained before the trigger.
            max_video_duration_seconds: Maximum clip duration, including pre-trigger frames.

        Returns:
            This configured node.
        """
        self.link_args(classifications, mjpeg_encoded_frames, h264_encoded_frames)
        self._event_store = event_store
        self._pre_trigger_duration_seconds = pre_trigger_duration_seconds
        self._max_video_duration_seconds = max_video_duration_seconds
        self._frame_buffer = EncodedVideoFrameBuffer(pre_trigger_duration_seconds)
        self._current_event_data: DangerTriggerEventData | None = None
        self._previous_level = DangerLevel.SAFE
        self._active_recording: H264VideoRecordingContainer | None = None
        self._fps = fps
        self._save_warning_events = save_warning_events
        self._save_danger_events = save_danger_events
        return self

    def process(
        self,
        classification: dai.Buffer,
        mjpeg_encoded_frame: dai.EncodedFrame,
        h264_encoded_frame: dai.EncodedFrame,
    ) -> None:
        assert isinstance(classification, DangerClassification)

        if self._has_entered_event(classification.level):
            self._current_event_data = self._create_event_data(
                mjpeg_encoded_frame=mjpeg_encoded_frame,
                event_type=self._event_type_for_level(classification.level),
            )
            self._active_recording = self._create_recording(
                self._current_event_data.triggered_at,
                h264_encoded_frame.getTimestamp().total_seconds(),
            )

        # Preserve the highest severity reached during this event.
        if (
            self._current_event_data is not None
            and classification.level == DangerLevel.DANGER
        ):
            self._current_event_data.event_type = DangerEventType.DANGER

        if (
            classification.level != DangerLevel.SAFE
            and self._active_recording is not None
        ):
            self._active_recording.add_frame(h264_encoded_frame)

        if (
            classification.level == DangerLevel.SAFE
            and self._current_event_data is not None
        ):
            self._finalize_current_event()
            self._current_event_data = None
            self._active_recording = None

        self._frame_buffer.append(h264_encoded_frame)
        self._previous_level = classification.level

    def _has_entered_event(self, level: DangerLevel) -> bool:
        return self._previous_level == DangerLevel.SAFE and level != DangerLevel.SAFE

    def _create_event_data(
        self,
        mjpeg_encoded_frame: dai.EncodedFrame,
        event_type: DangerEventType,
    ) -> DangerTriggerEventData:
        created_at = datetime.now(timezone.utc)
        try:
            img_path = self._save_jpg_image(mjpeg_encoded_frame, created_at)
        except Exception:
            logger.exception("Failed to save event image")
            img_path = None
        event_data = DangerTriggerEventData(
            frame_timestamp_seconds=mjpeg_encoded_frame.getTimestamp().total_seconds(),
            triggered_at=created_at,
            event_type=event_type,
            files=[],
        )
        if img_path is not None:
            event_data.files.append(
                DangerTriggerEventFileData(name="image", path=img_path)
            )
        return event_data

    def _create_recording(
        self, created_at: datetime, msg_timestamp: float
    ) -> H264VideoRecordingContainer:
        logger.info("Non-safe event started, beginning video capture")
        filename = self._build_video_filename(created_at)
        video_container = H264VideoRecordingContainer(
            filename,
            end_timestamp_seconds=self._recording_end_timestamp_seconds(msg_timestamp),
            files_dir=self._event_store.files_dir,
        )

        buffered_frames = self._frame_buffer.frames_for_trigger(
            trigger_timestamp_seconds=msg_timestamp
        )
        logger.info(
            f"Adding {len(buffered_frames)} frames from before the event to the recording"
        )
        video_container.add_frames(buffered_frames)
        return video_container

    def _recording_end_timestamp_seconds(
        self, trigger_timestamp_seconds: float
    ) -> float:
        post_trigger_duration_seconds = (
            self._max_video_duration_seconds - self._pre_trigger_duration_seconds
        )
        return trigger_timestamp_seconds + post_trigger_duration_seconds

    def _event_type_for_level(self, level: DangerLevel) -> DangerEventType:
        if level == DangerLevel.WARNING:
            return DangerEventType.WARNING
        if level == DangerLevel.DANGER:
            return DangerEventType.DANGER
        raise ValueError("Unknown danger level")

    def _is_event_type_enabled(self, event_type: DangerEventType) -> bool:
        if event_type == DangerEventType.WARNING:
            return self._save_warning_events
        if event_type == DangerEventType.DANGER:
            return self._save_danger_events
        raise ValueError("Unknown event type")

    def _finalize_current_event(self) -> None:
        if self._current_event_data is None:
            raise RuntimeError("No event data is available to save")

        if not self._is_event_type_enabled(self._current_event_data.event_type):
            logger.info(
                "Skipping %s event because saving is disabled",
                self._current_event_data.event_type.value,
            )
            self._discard_current_event()
            return

        if self._active_recording is not None:
            try:
                video_path = self._active_recording.filename
                self._active_recording.create_video_file(self._fps)
                self._current_event_data.files.append(
                    DangerTriggerEventFileData(name="video", path=video_path)
                )
            except Exception:
                logger.exception("Failed to capture event video")
        self._event_store.add(self._current_event_data)

    def _discard_current_event(self) -> None:
        if self._current_event_data is None:
            raise RuntimeError("No event data is available to discard")

        if self._active_recording is not None:
            self._active_recording.abort()

        for saved_file in self._current_event_data.files:
            self._delete_event_file(saved_file.path)

    def _save_jpg_image(
        self, encoded_frame: dai.EncodedFrame, created_at: datetime
    ) -> str:
        if encoded_frame.getProfile() != dai.EncodedFrame.Profile.JPEG:
            raise ValueError(
                "EventSaver expected a JPEG-encoded frame for event capture"
            )

        filename = self._build_image_filename(created_at)
        absolute_path: Path = self._event_store.files_dir / filename
        absolute_path.write_bytes(bytes(encoded_frame.getData()))
        return filename

    def _build_image_filename(self, created_at: datetime) -> str:
        timestamp = created_at.strftime("%Y%m%dT%H%M%S%fZ")
        filename = f"event-trigger-{timestamp}.jpg"
        return filename

    def _build_video_filename(self, created_at: datetime) -> str:
        timestamp = created_at.strftime("%Y%m%dT%H%M%S%fZ")
        filename = f"event-trigger-{timestamp}.mp4"
        return filename

    def _delete_event_file(self, relative_path: str) -> None:
        try:
            self._event_store.delete_file(relative_path)
        except FileNotFoundError:
            logger.warning(
                "Event file is unavailable during event discard: %s", relative_path
            )
        except OSError:
            logger.exception("Failed to remove discarded event file %s", relative_path)
