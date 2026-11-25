#!/usr/bin/env python3
import functools
import os
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import depthai as dai

from utils.arguments import initialize_argparser
from utils.board_config import resolve_mounting
from utils.calibrator_node import IMU_RATE_HZ, ImuCalibrator
from utils.device_info import has_magnetometer

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

imu_name = device.getConnectedIMU()
if imu_name in ("", "NONE"):
    raise SystemExit("This device has no IMU.")
mounting = resolve_mounting(device.readCalibration2(), imu_name, args.board_config)
print(f"IMU: {imu_name}, mounting from {mounting.source}")

with dai.Pipeline(device) as pipeline:
    camera = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_A)
    # H.264 keeps the link free for the IMU: raw NV12 frames delayed IMU packets by ~2 s on RVC4.
    encoder = pipeline.create(dai.node.VideoEncoder)
    encoder.setDefaultProfilePreset(15, dai.VideoEncoderProperties.Profile.H264_MAIN)
    camera.requestOutput((640, 400), dai.ImgFrame.Type.NV12, fps=15).link(encoder.input)
    visualizer.addTopic("Camera", encoder.out)

    imu = pipeline.create(dai.node.IMU)
    # RAW streams are in the sensor-native frame, so the stored extrinsics and calibration do not bias the fit.
    sensors = [dai.IMUSensor.ACCELEROMETER_RAW, dai.IMUSensor.GYROSCOPE_RAW]
    if has_magnetometer(imu_name):
        sensors.append(dai.IMUSensor.MAGNETOMETER_RAW)
    imu.enableIMUSensor(sensors, IMU_RATE_HZ)
    imu.setBatchReportThreshold(10)
    imu.setMaxBatchReports(10)

    calibrator = pipeline.create(ImuCalibrator).build(
        imu.out, device, mounting, args.output_dir, args.capture_seconds
    )
    visualizer.registerService(
        "IMU State", lambda request: calibrator.state(int(request.get("since", 0)))
    )
    visualizer.registerService(
        "IMU Action", lambda request: calibrator.action(str(request.get("action")))
    )

    pipeline.start()
    print("Pipeline started.")
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        if visualizer.waitKey(1) == ord("q"):
            break
