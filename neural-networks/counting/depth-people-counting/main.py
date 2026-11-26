import os
import tarfile
from pathlib import Path

import depthai as dai
from depthai_nodes.node import ApplyDepthColormap

from utils.arguments import initialize_argparser
from utils.disparity_to_dets import DisparityToDetections
from utils.annotation_node import AnnotationNode


_, args = initialize_argparser()


SIZE = (640, 400)
# Stream names written by enableHolisticRecord for these sockets.
REQUIRED_STREAMS = ("CameraCAM_B", "CameraCAM_C")


def _recording_names(path: Path) -> list[str]:
    if path.is_dir():
        return [
            item.relative_to(path).as_posix()
            for item in path.rglob("*")
            if item.is_file()
        ]
    if not tarfile.is_tarfile(path):
        raise SystemExit(
            f"{path} is not a holistic recording. record.py writes recording_<time>.tar.gz."
        )
    with tarfile.open(path, "r:*") as archive:
        return [member.name for member in archive.getmembers() if member.isfile()]


def _has_stream(names: list[str], stream: str) -> bool:
    for name in names:
        item = Path(name)
        if item.name.startswith(stream + ".") or item.parent.name == stream:
            return True
    return False


def require_holistic_recording(path: str) -> None:
    recording = Path(path)
    if not recording.exists():
        raise SystemExit(f"Replay path does not exist: {path}")
    names = _recording_names(recording)
    basenames = {Path(name).name for name in names}
    if "camera_info.json" not in basenames:
        raise SystemExit(
            "Holistic replay needs camera_info.json from record.py. "
            "That file carries the calibration and the camera list."
        )
    missing = [stream for stream in REQUIRED_STREAMS if not _has_stream(names, stream)]
    if missing:
        raise SystemExit(
            "Recording is missing "
            + ", ".join(missing)
            + ". record.py must be run on a device with CAM_B and CAM_C."
        )


replay_env = os.environ.get("DEPTHAI_REPLAY")
if args.media_path and replay_env:
    if Path(args.media_path).resolve() != Path(replay_env).resolve():
        raise SystemExit(
            "Pass either --media_path or DEPTHAI_REPLAY, not two different recordings."
        )
if args.media_path and os.environ.get("DEPTHAI_RECORD"):
    print("DEPTHAI_RECORD is ignored because --media_path enables replay.")

replay_path = args.media_path or replay_env
if replay_path:
    require_holistic_recording(replay_path)

visualizer = dai.RemoteConnection(httpPort=8082)
device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()
platform = device.getPlatformAsString()
print(f"Platform: {platform}")

with dai.Pipeline(device) as pipeline:
    print("Creating pipeline...")

    # Live and replay use the same cameras. enableHolisticReplay feeds the
    # recorded frames, calibration, and timestamps into these nodes.
    if args.media_path:
        pipeline.enableHolisticReplay(args.media_path)

    left = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_B)
    left_out = left.requestOutput(size=SIZE, type=dai.ImgFrame.Type.GRAY8)

    right = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_C)
    right_out = right.requestOutput(size=SIZE, type=dai.ImgFrame.Type.GRAY8)

    stereo = pipeline.create(dai.node.StereoDepth).build(left=left_out, right=right_out)
    stereo.initialConfig.setMedianFilter(dai.StereoDepthConfig.MedianFilter.KERNEL_7x7)
    stereo.setLeftRightCheck(True)
    stereo.setSubpixel(False)

    # people detector
    detection_generator = pipeline.create(DisparityToDetections).build(
        disparity=stereo.disparity,
        max_disparity=stereo.initialConfig.getMaxDisparity(),
        roi=(50, 50, 550, 350),
    )

    # object tracking
    objectTracker = pipeline.create(dai.node.ObjectTracker)
    if platform == "RVC2":
        objectTracker.setTrackerType(dai.TrackerType.ZERO_TERM_COLOR_HISTOGRAM)
    else:
        objectTracker.setTrackerType(dai.TrackerType.SHORT_TERM_IMAGELESS)
    objectTracker.setTrackerIdAssignmentPolicy(
        dai.TrackerIdAssignmentPolicy.SMALLEST_ID
    )

    color_transform_disparity = pipeline.create(ApplyDepthColormap).build(
        stereo.disparity
    )
    color_transform_disparity.out.link(objectTracker.inputTrackerFrame)
    color_transform_disparity.out.link(objectTracker.inputDetectionFrame)
    detection_generator.out.link(objectTracker.inputDetections)

    # annotation
    annotation_node = pipeline.create(AnnotationNode).build(
        objectTracker.out, axis=args.axis, axis_position=args.axis_position
    )

    # visualization
    visualizer.addTopic("Disparity", color_transform_disparity.out, "disparity")
    visualizer.addTopic("Count", annotation_node.out, "disparity")

    print("Pipeline created.")
    pipeline.start()
    print("Pipeline started.")
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got q key from the remote connection!")
            break
