import argparse
import os
import time
from pathlib import Path

import depthai as dai

parser = argparse.ArgumentParser()
parser.add_argument("--device", default=None, help="Device IP address")
parser.add_argument("--output", default="recordings", help="Output path")
parser.add_argument(
    "--duration",
    type=float,
    default=None,
    help="Stop after this many seconds. Without it, press q in the visualizer.",
)
parser.add_argument(
    "--fps",
    type=float,
    default=None,
    help="Camera rate to record. Omit it to keep the camera default. Lower it if the log says frames were skipped.",
)
args = parser.parse_args()
if args.duration is not None and args.duration <= 0:
    parser.error("--duration must be positive")
if args.fps is not None and args.fps <= 0:
    parser.error("--fps must be positive")

# Same size main.py requests. Holistic record may still write a larger aligned sensor mode.
SIZE = (640, 400)

# Create output directory
os.makedirs(args.output, exist_ok=True)

# Define visualization
visualizer = dai.RemoteConnection(httpPort=8082)

# Define device (by default, uses first connected)
device = (
    dai.Device(dai.DeviceInfo(args.device)) if args.device is not None else dai.Device()
)

# Create pipeline
with dai.Pipeline(device) as pipeline:
    # Define left stream
    output_args = {}
    if args.fps is not None:
        output_args["fps"] = args.fps

    camB = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_B)
    camBOut = camB.requestOutput(SIZE, **output_args)

    # Define right stream
    camC = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_C)
    camCOut = camC.requestOutput(SIZE, **output_args)

    # Define output
    config = dai.RecordConfig()
    config.outputDir = args.output
    config.videoEncoding.enabled = True
    config.videoEncoding.bitrate = 0  # Automatic
    config.videoEncoding.profile = dai.VideoEncoderProperties.Profile.H264_MAIN

    pipeline.enableHolisticRecord(config)

    # Visualize streams
    visualizer.addTopic("CamB", camBOut)
    visualizer.addTopic("CamC", camCOut)

    # Start pipeline
    pipeline.start()
    visualizer.registerPipeline(pipeline)

    print("Recording: START")
    deadline = None if args.duration is None else time.monotonic() + args.duration

    while pipeline.isRunning():
        if deadline is not None and time.monotonic() >= deadline:
            print("Recording: END")
            break
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Recording: END")
            break

archives = [
    entry
    for entry in Path(args.output).iterdir()
    if entry.is_file() and entry.name.startswith("recording_") and entry.name.endswith(".tar.gz")
]
if archives:
    newest = max(archives, key=lambda entry: entry.stat().st_mtime)
    print(f"Recording archive: {newest}")
else:
    print(f"Recording finished without a recording_*.tar.gz in {args.output}")
