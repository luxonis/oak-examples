import depthai as dai

# One-byte commands shared with the RVC2 device script. Start and STARTED
# share the value 1 because they travel on different inputs.
COMMAND_START = 1
STATUS_STOPPED = 0
STATUS_ERROR = 2


def command_buffer(code: int) -> dai.Buffer:
    """A Buffer whose first byte and sequence number are both `code`."""
    message = dai.Buffer()
    message.setSequenceNum(code)
    message.setData(bytes([code & 0xFF]))
    return message


def command_code(message: dai.Buffer) -> int:
    data = message.getData()
    if data is not None and len(data) > 0:
        return int(data[0])
    return int(message.getSequenceNum())


def status_code(state: dai.RecordStatus.State) -> int:
    if state == dai.RecordStatus.State.STARTED:
        return COMMAND_START
    if state == dai.RecordStatus.State.ERROR:
        return STATUS_ERROR
    return STATUS_STOPPED


class RecordCommandBridge(dai.node.HostNode):
    """Turns RVC2 script Buffer commands into RecordControl.

    Stock RVC2 script firmware can build a Buffer. It cannot build
    RecordControl, so the script decides and this node sends the real message.
    """

    def __init__(self) -> None:
        super().__init__()
        self._queue = None
        self._max_frames = -1
        self._max_duration_ms = -1
        self._max_size_kb = -1

    def build(
        self,
        commands: dai.Node.Output,
        record: dai.node.RecordVideo,
        max_frames: int,
        max_duration_ms: int,
        max_size_kb: int,
    ) -> "RecordCommandBridge":
        self.link_args(commands)
        self._queue = record.inputControl.createInputQueue()
        self._max_frames = max_frames
        self._max_duration_ms = max_duration_ms
        self._max_size_kb = max_size_kb
        return self

    def process(self, command: dai.Buffer) -> None:
        if self._queue is None:
            return
        if command_code(command) == COMMAND_START:
            print("record bridge: start")
            self._queue.send(
                dai.RecordControl.start(
                    self._max_frames, self._max_duration_ms, self._max_size_kb
                )
            )
        else:
            print("record bridge: stop")
            self._queue.send(dai.RecordControl.stop())
