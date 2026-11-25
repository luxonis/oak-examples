import av
import depthai as dai

# Encoded messages kept while waiting for their decoded frame. PyAV's default
# slice threading returns frames within a few packets; raise this if you enable
# frame threading, which delays output by about one frame per thread.
MAX_PENDING = 16


class DecodeVideoAv(dai.node.HostNode):
    def __init__(self) -> None:
        super().__init__()

        self._out = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.ImgFrame, True)
            ]
        )
        self.verbose = False
        # Encoded messages waiting for their decoded frame, keyed by packet PTS.
        self._pending = {}
        self._next_pts = 0

    def build(self, enc_out, codec) -> "DecodeVideoAv":
        self.codec = av.CodecContext.create(codec, "r")
        self.link_args(enc_out)
        self.inputs["enc_vid"].setMaxSize(1)
        self.inputs["enc_vid"].setBlocking(True)
        return self

    def process(self, enc_vid) -> None:
        # VideoEncoder emits one complete frame per message, so each message is
        # decoded as its own packet. Decoders may return a frame later (HEVC
        # holds a few back), so each packet gets its own PTS and each decoded
        # frame keeps the metadata of the message with that PTS.
        packet = av.Packet(enc_vid.getData().tobytes())
        packet.pts = self._next_pts
        self._next_pts += 1
        self._pending[packet.pts] = enc_vid
        try:
            frames = self.codec.decode(packet)
        except av.error.FFmpegError:
            del self._pending[packet.pts]  # skip a corrupt packet
            return
        for frame in frames:
            img = dai.ImgFrame()
            img.setCvFrame(frame.to_ndarray(format="bgr24"), dai.ImgFrame.Type.BGR888p)
            source = self._pending.pop(frame.pts, None)
            if source is not None:
                img.setBufferMetadataFrom(source)
                img.setTransformation(source.getTransformation())
            self.out.send(img)

        # Forget the oldest messages if the decoder never returned their frames.
        while len(self._pending) > MAX_PENDING:
            del self._pending[next(iter(self._pending))]

    @property
    def out(self) -> dai.Node.Output:
        return self._out
