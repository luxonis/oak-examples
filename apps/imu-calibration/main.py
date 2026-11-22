#!/usr/bin/env python3
import depthai as dai

from utils.arguments import initialize_argparser
from utils.board_config import resolve_mounting
from utils.calibrator_node import IMU_RATE_HZ, ImuCalibrator

_, args = initialize_argparser()

visualizer = dai.RemoteConnection(httpPort=8082)
device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()

imu_name = device.getConnectedIMU()
if imu_name in ("", "NONE"):
    raise SystemExit("This device has no IMU.")
mounting = resolve_mounting(device.readCalibration2(), imu_name, args.board_config)
print(f"IMU: {imu_name}, mounting from {mounting.source}")

with dai.Pipeline(device) as pipeline:
    imu = pipeline.create(dai.node.IMU)
    # RAW streams are in the sensor-native frame, so the stored extrinsics and calibration do not bias the fit.
    imu.enableIMUSensor(
        [dai.IMUSensor.ACCELEROMETER_RAW, dai.IMUSensor.GYROSCOPE_RAW], IMU_RATE_HZ
    )
    imu.setBatchReportThreshold(10)
    imu.setMaxBatchReports(10)

    calibrator = pipeline.create(ImuCalibrator).build(
        imu.out, device, mounting, args.output_dir, args.capture_seconds
    )
    visualizer.addTopic("IMU Calibration", calibrator.out)

    pipeline.start()
    print("Pipeline started.")
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        key = visualizer.waitKey(1)
        if key == ord("q"):
            break
        if key != -1:
            calibrator.keys.put(key)
