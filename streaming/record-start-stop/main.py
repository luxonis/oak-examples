from pathlib import Path

import depthai as dai

from utils.arguments import initialize_argparser
from utils.record_bridge import (
    COMMAND_START,
    STATUS_STOPPED,
    RecordCommandBridge,
    command_buffer,
    status_code,
)
from utils.recording_indicator import RecordingIndicator
from utils.trigger_script import build_trigger_script

TARGET_MODELS = {
    "person": "yolov6_nano_r2_coco",
    "face": "yunet",
}
TARGET_LABELS = {
    "person": "person",
    "face": "face",
}

_, args = initialize_argparser()

visualizer = dai.RemoteConnection(httpPort=8082)
device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()
platform = device.getPlatform().name
print(f"Platform: {platform}")

if args.fps_limit is None:
    args.fps_limit = 20 if platform == "RVC2" else 30
    print(
        f"\nFPS limit set to {args.fps_limit} for {platform} platform. If you want to set a custom FPS limit, use the --fps_limit flag.\n"
    )

fps = args.fps_limit
output_dir = Path(args.output_dir)
output_dir.mkdir(parents=True, exist_ok=True)
recording_name = "start-stop_" + dai.makeRecordingTimestamp()
wanted_labels = [
    part.strip().lower()
    for part in (args.label or TARGET_LABELS[args.target]).split(",")
    if part.strip()
]


def status_text(status: dai.RecordStatus) -> str:
    names = {
        dai.RecordStatus.State.STARTED: "STARTED",
        dai.RecordStatus.State.STOPPED: "STOPPED",
        dai.RecordStatus.State.ERROR: "ERROR",
    }
    state = names.get(status.state, "UNKNOWN")
    text = (
        f"status {state} segment={status.segment} frames={status.frameCount} "
        f"seq={status.firstSequenceNum}..{status.lastSequenceNum} "
        f"skipped={status.skippedFrames} path={status.path}"
    )
    if status.error:
        text += f" error={status.error}"
    return text


def matching_labels(classes: list[str]) -> tuple[list[str], list[int]]:
    names = []
    indexes = []
    for index, name in enumerate(classes):
        lowered = str(name).lower()
        if lowered in wanted_labels:
            names.append(lowered)
            indexes.append(index)
    return names, indexes


with dai.Pipeline(device) as pipeline:
    print("Creating pipeline...")

    if args.model:
        model_description = dai.NNModelDescription(args.model, platform=platform)
    else:
        model_description = dai.NNModelDescription.fromYamlFile(
            f"{TARGET_MODELS[args.target]}.{platform}.yaml"
        )
    nn_archive = dai.NNArchive(dai.getModelFromZoo(model_description))
    nn_size = nn_archive.getInputSize()
    width, height = int(nn_size[0]), int(nn_size[1])
    if platform == "RVC2" and (width % 32 != 0 or height % 8 != 0):
        raise SystemExit(
            f"Model input {width}x{height} cannot be H.264 encoded on RVC2. "
            "Width must be a multiple of 32 and height a multiple of 8."
        )

    cam = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_A)
    nn = pipeline.create(dai.node.DetectionNetwork).build(
        cam, nnArchive=nn_archive, fps=float(fps)
    )
    classes = [str(name) for name in (nn.getClasses() or [])]
    print(f"Classes: {', '.join(classes) if classes else '(none)'}")

    label_names: list[str] = []
    label_indexes: list[int] = []
    if args.auto_record:
        if classes:
            label_names, label_indexes = matching_labels(classes)
            if not label_indexes:
                raise SystemExit(
                    "None of the auto-record labels "
                    f"{wanted_labels} are in this model. Classes: {classes}."
                )
        else:
            print(
                "Model has no class names. Any detection starts a recording "
                f"for labels {wanted_labels}."
            )
        print(
            "Auto record labels: "
            + (", ".join(label_names) if label_names else "(any detection)")
        )

    encode_manip = pipeline.create(dai.node.ImageManip)
    encode_manip.setMaxOutputFrameSize(width * height * 3)
    encode_manip.initialConfig.setOutputSize(width, height)
    encode_manip.initialConfig.setFrameType(dai.ImgFrame.Type.NV12)
    nn.passthrough.link(encode_manip.inputImage)

    encoder = pipeline.create(dai.node.VideoEncoder)
    encoder.setMaxOutputFrameSize(width * height * 3)
    encoder.setDefaultProfilePreset(fps, dai.VideoEncoderProperties.Profile.H264_MAIN)
    encode_manip.out.link(encoder.input)

    record = pipeline.create(dai.node.RecordVideo)
    record.setOutputDirectory(output_dir)
    record.setRecordingName(recording_name)
    record.setFps(fps)
    record.setWaitForTrigger(True)
    record.setPreTriggerFrames(args.pretrigger_frames)
    encoder.out.link(record.input)

    indicator = pipeline.create(RecordingIndicator).build(
        frames=nn.passthrough,
        record=record,
        auto_record=args.auto_record,
        frame_size=(width, height),
    )

    # RVC2 script firmware can build Buffer, not RecordControl. The script still
    # decides. A host node turns those bytes into RecordControl.
    script_commands_are_buffers = args.auto_record and platform == "RVC2"
    status_queue = None
    if args.auto_record:
        script = pipeline.create(dai.node.Script)
        script.setScript(
            build_trigger_script(
                label_names,
                label_indexes,
                args.max_frames,
                args.max_duration_ms,
                args.max_size_kb,
                native_control=not script_commands_are_buffers,
            ),
            "record_trigger",
        )
        nn.out.link(script.inputs["detections"])
        script.inputs["detections"].setBlocking(False)
        script.inputs["detections"].setMaxSize(4)
        script.inputs["manual"].setBlocking(False)
        script.inputs["manual"].setMaxSize(4)
        script.inputs["status"].setBlocking(False)
        script.inputs["status"].setMaxSize(8)
        control_queue = script.inputs["manual"].createInputQueue(4, False)
        if script_commands_are_buffers:
            print(
                "RVC2 script nodes cannot construct RecordControl. "
                "A host node translates the script commands."
            )
            status_queue = script.inputs["status"].createInputQueue(8, False)
            script.outputs["control"].setPossibleDatatypes(
                [(dai.DatatypeEnum.Buffer, False)]
            )
            pipeline.create(RecordCommandBridge).build(
                commands=script.outputs["control"],
                record=record,
                max_frames=args.max_frames,
                max_duration_ms=args.max_duration_ms,
                max_size_kb=args.max_size_kb,
            )
        else:
            record.status.link(script.inputs["status"])
            script.outputs["control"].setPossibleDatatypes(
                [(dai.DatatypeEnum.RecordControl, False)]
            )
            script.outputs["control"].link(record.inputControl)
    else:
        control_queue = record.inputControl.createInputQueue()

    visualizer.addTopic("Video", nn.passthrough, "images")
    visualizer.addTopic("Detections", nn.out, "images")
    visualizer.addTopic("Recording", indicator.output, "images")

    print("Pipeline created.")
    pipeline.start()
    print("Pipeline started.")
    visualizer.registerPipeline(pipeline)

    recording_dir = output_dir / recording_name
    print(f"RecordVideo runOnHost={record.runOnHost()}")
    print(f'Saving video to "{recording_dir / "frames.mp4"}"')
    print(f'Saving metadata to "{recording_dir / "frames.mcap"}"')
    print(
        f"Limits: frames={args.max_frames} duration_ms={args.max_duration_ms} "
        f"size_kb={args.max_size_kb} pretrigger={args.pretrigger_frames}"
    )
    if not record.runOnHost():
        print(
            "The device keeps the recording until the pipeline stops, then copies it here."
        )
    print("Press r (or space) in the visualizer to start or stop. Press q to quit.")

    def send_manual(start: bool) -> None:
        if script_commands_are_buffers:
            control_queue.send(
                command_buffer(COMMAND_START if start else STATUS_STOPPED)
            )
        elif start:
            control_queue.send(
                dai.RecordControl.start(
                    args.max_frames, args.max_duration_ms, args.max_size_kb
                )
            )
        else:
            control_queue.send(dai.RecordControl.stop())

    last_status = None
    # The script already starts idle. Forward status only after the node has
    # started once, so the initial STOPPED does not cancel a detection start.
    forward_status = False
    while pipeline.isRunning():
        status = record.getStatus()
        if status is not None and (
            last_status is None
            or status.getSequenceNum() != last_status.getSequenceNum()
            or status.state != last_status.state
        ):
            print(status_text(status))
            last_status = status
            if status.state == dai.RecordStatus.State.STARTED:
                forward_status = True
            if status_queue is not None and forward_status:
                status_queue.send(command_buffer(status_code(status.state)))

        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got q key from the remote connection!")
            break
        if key in (ord("r"), ord(" ")):
            recording_now = (
                status is not None and status.state == dai.RecordStatus.State.STARTED
            )
            if recording_now:
                print("sending stop()")
                send_manual(False)
            else:
                print("sending start()")
                send_manual(True)
