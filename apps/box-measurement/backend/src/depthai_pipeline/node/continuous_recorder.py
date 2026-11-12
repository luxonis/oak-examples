import logging
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from pathlib import Path

import av
import depthai as dai

from util.recording_files import RECORDINGS_DIR

logger = logging.getLogger(__name__)

_TIME_BASE = Fraction(1, 1_000_000)


class ChunkedH264Writer:
    """Streams encoded H264 frames into rolling, keyframe-aligned mp4 chunks.
    A new chunk only starts on an I-frame, so every chunk is independently playable.
    """

    def __init__(self, output_dir: Path, chunk_length_sec: int, fps: int):
        self._output_dir = output_dir
        self._chunk_length_sec = chunk_length_sec
        self._fps = fps
        self._container: av.container.OutputContainer | None = None
        self._stream: av.video.stream.VideoStream | None = None
        self._chunk_epoch: timedelta | None = None  # timestamp of first frame
        self._chunk_start_sec: float | None = None
        self._temp_path: Path | None = None
        self._final_path: Path | None = None
        self._sweep_orphan_chunks()

    def _sweep_orphan_chunks(self) -> None:
        # Remove unfinalized chunks left by a previous ungraceful stop/crash
        if not self._output_dir.is_dir():
            return
        for orphan in self._output_dir.glob("recording-*.mp4.part"):
            orphan.unlink(missing_ok=True)

    def add_frame(self, frame: dai.EncodedFrame) -> None:
        timestamp_sec = frame.getTimestamp().total_seconds()
        is_keyframe = frame.getFrameType() == dai.EncodedFrame.FrameType.I

        # Rotate at a keyframe once the current chunk is long enough.
        if (
            self._container is not None
            and is_keyframe
            and self._chunk_start_sec is not None
            and timestamp_sec - self._chunk_start_sec >= self._chunk_length_sec
        ):
            self.close()

        # A chunk can only start on a keyframe
        if self._container is None:
            if not is_keyframe:
                return
            self._open_chunk(frame)

        self._mux(frame)

    def _open_chunk(self, frame: dai.EncodedFrame) -> None:
        self._output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        # Record into a .part file; rename to .mp4 only once finalized
        self._final_path = self._output_dir / f"recording-{timestamp}.mp4"
        self._temp_path = self._output_dir / f"recording-{timestamp}.mp4.part"
        self._container = av.open(str(self._temp_path), "w", format="mp4")
        stream = self._container.add_stream("h264", rate=self._fps)
        stream.time_base = _TIME_BASE
        stream.width = frame.getWidth()
        stream.height = frame.getHeight()
        self._stream = stream
        self._chunk_epoch = frame.getTimestamp()
        self._chunk_start_sec = frame.getTimestamp().total_seconds()
        logger.info("Started continuous recording chunk %s", self._final_path.name)

    def _mux(self, frame: dai.EncodedFrame) -> None:
        if (
            self._container is None
            or self._stream is None
            or self._chunk_epoch is None
        ):
            return
        packet = av.Packet(frame.getData().tobytes())
        offset = (frame.getTimestamp() - self._chunk_epoch).total_seconds()
        packet.pts = int(offset * 1_000_000)
        packet.dts = packet.pts
        packet.time_base = _TIME_BASE
        packet.stream = self._stream
        self._container.mux(packet)

    def close(self) -> None:
        if self._container is None:
            return
        try:
            self._container.close()
            if self._temp_path is not None and self._final_path is not None:
                self._temp_path.rename(self._final_path)
                logger.info(
                    "Finalized continuous recording chunk %s",
                    self._final_path.name,
                )
        except Exception:
            logger.exception("Failed to finalize continuous recording chunk")
        finally:
            self._container = None
            self._stream = None
            self._chunk_epoch = None
            self._chunk_start_sec = None
            self._temp_path = None
            self._final_path = None


class ContinuousRecorder(dai.node.HostNode):
    """Continuous chunked recording of the color H264 stream."""

    def build(
        self,
        h264_encoded_frames: dai.Node.Output,
        fps: int,
        chunk_length_sec: int,
    ) -> "ContinuousRecorder":
        self.link_args(h264_encoded_frames)
        self._writer = ChunkedH264Writer(RECORDINGS_DIR, chunk_length_sec, fps)
        return self

    def process(self, h264_encoded_frame: dai.Buffer) -> None:
        assert isinstance(h264_encoded_frame, dai.EncodedFrame)
        self._writer.add_frame(h264_encoded_frame)

    def onStop(self) -> None:
        self._writer.close()
