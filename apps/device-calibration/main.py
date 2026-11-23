#!/usr/bin/env python3
import functools
import os
import threading
from datetime import timedelta
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import depthai as dai

from utils.arguments import initialize_argparser
from utils.board_config import load_boards
from utils.capture_node import CaptureNode, DatasetReplay
from utils.device_info import has_magnetometer
from utils.imu_node import IMU_RATE_HZ, ImuCalibrator
from utils.session import Session

FRONTEND_PORT = 8082
FRONTEND_DIST = Path(__file__).parent / "frontend" / "dist"

_, args = initialize_argparser()

# Standalone (RVC4): the OAK agent serves the static frontend. Peripheral: serve the local build.
if "OAKAPP_STATIC_FRONTEND_PATH" not in os.environ:
    if (FRONTEND_DIST / "index.html").exists():
        handler = functools.partial(
            SimpleHTTPRequestHandler, directory=str(FRONTEND_DIST)
        )
        try:
            server = ThreadingHTTPServer(("0.0.0.0", FRONTEND_PORT), handler)
        except OSError as e:
            raise SystemExit(
                f"Port {FRONTEND_PORT} is in use ({e.strerror}); stop the other app instance first."
            )
        threading.Thread(target=server.serve_forever, daemon=True).start()
        print(f"Open http://localhost:{FRONTEND_PORT} in your browser")
    else:
        print("Frontend not built; run `npm install && npm run build` in frontend/.")

visualizer = dai.RemoteConnection(serveFrontend=False)
device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()
FPS = args.capture_fps
# 960 px made three cameras exceed a 100 Mbit link (1.7 groups/s); 640 px gives 5.3 groups/s at 6 fps.
LIVE_WIDTH = 640
NV12 = dai.ImgFrame.Type.NV12
SENSOR_TYPES = dai.CameraSensorType
boards = load_boards(args.boards_dir, args.output_dir)
features = device.getConnectedCameraFeatures()
imu_name = device.getConnectedIMU()
has_imu = imu_name not in ("", "NONE")


def new_gate(pipeline: dai.Pipeline, out: dai.Node.Output):
    """A gate that starts closed; returns it and the queue that drives it."""
    gate = pipeline.create(dai.node.Gate)
    gate.initialConfig.open = False
    out.link(gate.input)
    return gate, gate.inputControl.createInputQueue()


def replay_names() -> dict:
    """socket -> dataset folder, for any camera name a depthai-boards entry gives a connected socket."""
    found: dict = {}
    connected = {f.socket.name for f in features}
    for name in boards.names:
        for socket, cam in boards.get(name)["cameras"].items():
            if socket in connected and (args.replay_dataset / cam["name"]).is_dir():
                found.setdefault(socket, cam["name"])
    return found


with dai.Pipeline(device) as pipeline:
    live_gates, full_gates = {}, {}
    cameras = [f for f in features if f.supportedTypes[0] in (SENSOR_TYPES.COLOR, SENSOR_TYPES.MONO)]
    # H.264 keeps the link free for the IMU: raw NV12 frames delayed IMU packets by ~2 s on RVC4.
    preview = next((f for f in cameras if f.supportedTypes[0] == SENSOR_TYPES.COLOR), cameras[0] if cameras else None)
    if preview:
        # The other cameras run at the capture fps; a 15 fps sensor still syncs with them.
        camera = pipeline.create(dai.node.Camera).build(preview.socket, sensorFps=15)
        encoder = pipeline.create(dai.node.VideoEncoder)
        encoder.setDefaultProfilePreset(15, dai.VideoEncoderProperties.Profile.H264_MAIN)
        camera.requestOutput((640, 400), NV12, fps=15).link(encoder.input)
        visualizer.addTopic("Camera", encoder.out)

    if args.replay_dataset:
        names = replay_names()
        if not names:
            raise SystemExit(f"{args.replay_dataset} has no camera folders matching a depthai-boards camera name.")
        # A set must stay long enough for 3 still groups; detecting a dense board takes ~1 s per group.
        replay = pipeline.create(DatasetReplay).build(args.replay_dataset, names, fps=FPS, set_seconds=6.0)
        capture = pipeline.create(CaptureNode).build(replay.live_out, replay.full_out, list(names), replay.request_full)
    else:
        live_sync = pipeline.create(dai.node.Sync)
        live_sync.setSyncThreshold(timedelta(milliseconds=50))
        full_sync = pipeline.create(dai.node.Sync)
        full_sync.setSyncThreshold(timedelta(seconds=0.5 / FPS))
        for f in features:
            kind = f.supportedTypes[0]
            if kind in (SENSOR_TYPES.COLOR, SENSOR_TYPES.MONO):
                cam = camera if f is preview else pipeline.create(dai.node.Camera).build(f.socket, sensorFps=FPS)
                width = min(f.width, LIVE_WIDTH)
                live = cam.requestOutput((width, round(f.height * width / f.width / 2) * 2), NV12, fps=FPS)
                full = cam.requestFullResolutionOutput(type=NV12, fps=FPS)
            else:  # ToF amplitude / thermal color frames are small, so one output feeds both tiers
                live = full = (
                    pipeline.create(dai.node.ToF).build(f.socket, fps=FPS).amplitude
                    if kind == SENSOR_TYPES.TOF
                    else pipeline.create(dai.node.Thermal).build(f.socket, FPS).color
                )
            for tier, out, sync in ((live_gates, live, live_sync), (full_gates, full, full_sync)):
                gate, tier[f.socket.name] = new_gate(pipeline, out)
                gate.output.link(sync.inputs[f.socket.name])
        # Three frames per camera make Sync pair reliably, but only the first group may cross the link.
        group_gate, group_control = new_gate(pipeline, full_sync.out)

        def request_full(_: list) -> None:
            # Sync waits for every input, so all cameras deliver; CaptureNode keeps only the ones that saw the board.
            group_control.send(dai.GateControl.openGate(1))
            for queue in full_gates.values():
                queue.send(dai.GateControl.openGate(3, FPS))

        capture = pipeline.create(CaptureNode).build(
            live_sync.out, group_gate.output, list(live_gates), request_full
        )
    for socket, out in capture.previews.items():
        visualizer.addTopic(socket, out)

    calibrator = None
    if has_imu:
        imu = pipeline.create(dai.node.IMU)
        # RAW streams are in the sensor-native frame, so the stored extrinsics and calibration do not bias the fit.
        sensors = [dai.IMUSensor.ACCELEROMETER_RAW, dai.IMUSensor.GYROSCOPE_RAW]
        if has_magnetometer(imu_name):
            sensors.append(dai.IMUSensor.MAGNETOMETER_RAW)
        imu.enableIMUSensor(sensors, IMU_RATE_HZ)
        imu.setBatchReportThreshold(10)
        imu.setMaxBatchReports(10)
        calibrator = pipeline.create(ImuCalibrator).build(imu.out, args.capture_seconds)

    session = Session(device, boards, capture, calibrator, live_gates, args)
    print(f"IMU: {imu_name or 'none'}, mounting from {session.mounting.source}")
    visualizer.registerService("Calibration State", lambda request: session.state(int(request.get("since", 0))))
    visualizer.registerService("Calibration Action", session.action)
    visualizer.registerService("Board Preview", session.board_preview)

    pipeline.start()
    print("Pipeline started.")
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        if visualizer.waitKey(1) == ord("q"):
            break
