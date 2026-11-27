from fractions import Fraction
from typing import Tuple

import depthai as dai


class VideoSaver(dai.node.ThreadedHostNode):
    """PyAV muxer for the codecs and containers RecordVideo does not write.

    RecordVideo writes H.264 and MJPEG, and only into a file whose extension is
    ``.mp4``. H.265 and every other container stay here. ``run`` closes the
    container when it leaves, including after the pipeline stops this input, so
    the file trailer is written.
    """

    def __init__(self) -> None:
        super().__init__()
        # The previous HostNode Sync input was non-blocking with room for 10 frames.
        self.input = self.createInput(
            blocking=False,
            queueSize=10,
            types=[dai.Node.DatatypeHierarchy(dai.DatatypeEnum.EncodedFrame, False)],
        )
        self.output_container = None
        self.stream = None
        self.start_time = None

    def build(
        self,
        encoded_stream: dai.Node.Output,
        codec: str,
        output_shape: Tuple[int, int],
        fps: int,
        output_path: str,
    ) -> "VideoSaver":
        # Imported here so the H.264 and MJPEG ``.mp4`` path does not need PyAV.
        import av

        encoded_stream.link(self.input)
        self._av = av
        self.output_container = av.open(output_path, "w")

        if codec == "h265":
            self.stream = self.output_container.add_stream("hevc", rate=fps)
        else:
            self.stream = self.output_container.add_stream(codec, rate=fps)

        if codec == "mjpeg":
            # We need to set pixel format for MJPEG, for H264/H265 it's yuv420p by default
            self.stream.pix_fmt = "yuvj420p"

        # Microseconds. The muxer may replace stream.time_base (Matroska uses
        # 1/1000 after the first packet), so each packet keeps this value.
        self._time_base = Fraction(1, 1_000_000)
        self.stream.time_base = self._time_base
        self.stream.width = output_shape[0]
        self.stream.height = output_shape[1]
        self.start_time = None

        return self

    def run(self) -> None:
        try:
            while self.mainLoop():
                encoded_frame = self.input.get()
                self._write(encoded_frame)
        except dai.MessageQueue.QueueException:
            # The pipeline closes this input on stop.
            pass
        finally:
            self._close()

    def _write(self, encoded_frame: dai.EncodedFrame) -> None:
        data = encoded_frame.getData()
        # Create new packet with byte array (we can do this because the data is already encoded)
        packet = self._av.Packet(data)

        # Set frame timestamp
        if self.start_time is None:
            self.start_time = encoded_frame.getTimestamp()
        timestamp = int(
            (encoded_frame.getTimestamp() - self.start_time).total_seconds() * 1_000_000
        )

        packet.pts = timestamp
        packet.dts = timestamp
        packet.time_base = self._time_base
        packet.stream = self.stream

        # Mux the packet into container
        self.output_container.mux(packet)

    def _close(self) -> None:
        container = self.output_container
        self.output_container = None
        if container is not None:
            container.close()
