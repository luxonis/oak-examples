"""Device script that starts and stops a recording from detections.

The record node closes a segment when a start limit is reached. This script
decides when to send start and stop. On RVC4 it sends RecordControl. On RVC2
the script firmware has no RecordControl type, so it sends a one-byte Buffer
and the host bridge turns that into RecordControl.
"""

import textwrap

ABSENCE_SECONDS = 2.0


def _python_tuple(values: list, quote: bool) -> str:
    if quote:
        body = ", ".join(repr(str(value)) for value in values)
    else:
        body = ", ".join(str(int(value)) for value in values)
    if len(values) == 1:
        return f"({body},)"
    return f"({body})"


def _script_io(native_control: bool) -> str:
    if native_control:
        return textwrap.dedent(
            """\
            START = RecordControl.Command.START
            STOPPED = RecordStatus.State.STOPPED
            ERROR = RecordStatus.State.ERROR

            def manual_limits(message):
                return message.maxFrames, message.maxDurationMs, message.maxSizeKb

            def is_start(message):
                return message.command == START

            def has_ended(message):
                return message.state == STOPPED or message.state == ERROR

            def send_start(max_frames, max_duration_ms, max_size_kb):
                node.outputs["control"].send(
                    RecordControl.start(max_frames, max_duration_ms, max_size_kb)
                )

            def send_stop():
                node.outputs["control"].send(RecordControl.stop())
            """
        )

    from utils.record_bridge import COMMAND_START, STATUS_ERROR, STATUS_STOPPED

    return textwrap.dedent(
        f"""\
        START = {COMMAND_START}
        STOPPED = {STATUS_STOPPED}
        ERROR = {STATUS_ERROR}

        def message_code(message):
            data = message.getData()
            if data is not None and len(data) > 0:
                return int(data[0])
            return int(message.getSequenceNum())

        def manual_limits(message):
            return MAX_FRAMES, MAX_DURATION_MS, MAX_SIZE_KB

        def is_start(message):
            return message_code(message) == START

        def has_ended(message):
            return message_code(message) == STOPPED or message_code(message) == ERROR

        def send_code(code):
            message = Buffer(1)
            message.setSequenceNum(code)
            message.setData(bytes([code]))
            node.outputs["control"].send(message)

        def send_start(max_frames, max_duration_ms, max_size_kb):
            send_code(START)

        def send_stop():
            send_code(STOPPED)
        """
    )


def build_trigger_script(
    label_names: list[str],
    label_indexes: list[int],
    max_frames: int,
    max_duration_ms: int,
    max_size_kb: int,
    native_control: bool,
) -> str:
    """Return the script source. An empty label list matches every detection."""
    labels = _python_tuple(label_names, quote=True)
    indexes = _python_tuple(label_indexes, quote=False)
    header = textwrap.dedent(
        f"""\
        import time

        LABELS = {labels}
        INDEXES = {indexes}
        MAX_FRAMES = {int(max_frames)}
        MAX_DURATION_MS = {int(max_duration_ms)}
        MAX_SIZE_KB = {int(max_size_kb)}
        ABSENCE_S = {ABSENCE_SECONDS}
        """
    ).rstrip("\n")
    loop = textwrap.dedent(
        """\
        recording = False
        manual_hold = False
        suppressed = False
        last_seen = None


        def matches(detection):
            if not LABELS and not INDEXES:
                return True
            name = detection.labelName.lower() if detection.labelName else ""
            if name and name in LABELS:
                return True
            return detection.label in INDEXES


        while True:
            now = time.monotonic()

            manual = node.inputs["manual"].tryGet()
            while True:
                newer = node.inputs["manual"].tryGet()
                if newer is None:
                    break
                manual = newer
            if manual is not None:
                if is_start(manual):
                    frames, duration_ms, size_kb = manual_limits(manual)
                    send_start(frames, duration_ms, size_kb)
                    recording = True
                    manual_hold = True
                    suppressed = False
                    node.warn("manual start")
                else:
                    send_stop()
                    recording = False
                    manual_hold = False
                    suppressed = True
                    last_seen = now
                    node.warn("manual stop")

            status = node.inputs["status"].tryGet()
            while status is not None:
                if has_ended(status):
                    ended = recording
                    recording = False
                    manual_hold = False
                    if ended:
                        node.warn("record stopped")
                else:
                    recording = True
                status = node.inputs["status"].tryGet()

            seen = False
            message = node.inputs["detections"].tryGet()
            while message is not None:
                for detection in message.detections:
                    if matches(detection):
                        seen = True
                        break
                message = node.inputs["detections"].tryGet()

            if seen:
                last_seen = now
                if not recording and not suppressed:
                    send_start(MAX_FRAMES, MAX_DURATION_MS, MAX_SIZE_KB)
                    recording = True
                    manual_hold = False
                    node.warn("auto start")

            if last_seen is not None and (now - last_seen) >= ABSENCE_S:
                suppressed = False
                if recording and not manual_hold:
                    send_stop()
                    recording = False
                    last_seen = None
                    node.warn("auto stop")

            time.sleep(0.05)
        """
    ).rstrip("\n")
    return f"{header}\n{_script_io(native_control).rstrip(chr(10))}\n\n{loop}\n"
