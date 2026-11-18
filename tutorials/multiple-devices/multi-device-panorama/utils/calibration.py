from datetime import timedelta
from pathlib import Path
from typing import List, Optional

import depthai as dai

STEREO_SOCKETS = (dai.CameraBoardSocket.CAM_B, dai.CameraBoardSocket.CAM_C)
CALIBRATION_FPS = 5


def select_devices(
    devices: List[str],
    include_ip: bool = False,
    max_devices: Optional[int] = None,
) -> List[dai.DeviceInfo]:
    """Return the devices named on the command line, or discover them.

    Discovery skips IP-only devices (e.g. OAK-4) unless include_ip is set, so a
    shared network full of cameras is not opened by accident.
    """
    if devices:
        return [dai.DeviceInfo(device) for device in devices]

    infos = dai.Device.getAllAvailableDevices()
    if not include_ip:
        infos = [
            info for info in infos if info.protocol != dai.XLinkProtocol.X_LINK_TCP_IP
        ]
    if max_devices is not None and len(infos) > max_devices:
        print(f"Using the first {max_devices} of {len(infos)} discovered devices.")
        infos = infos[:max_devices]
    return infos


def calibrate(
    device_infos: List[dai.DeviceInfo],
    output: Path,
    sample_count: int,
    known_distance: Optional[float],
) -> None:
    """Estimate the poses between the devices with MultiDeviceCalibration and save them as JSON."""
    with dai.Pipeline(createImplicitDevice=False) as pipeline:
        calibration = pipeline.create(dai.beta.node.MultiDeviceCalibration)
        calibration.setSampleCount(sample_count)
        # The devices are free-running; a static scene tolerates capture offsets between them.
        calibration.sync.setSyncThreshold(timedelta(seconds=5))

        first_cameras = []
        for info in device_infos:
            device = pipeline.addDevice(info)
            device_id = device.getDeviceId()
            connected = device.getConnectedCameras()
            # A factory-calibrated stereo pair fixes the metric scale; single cameras need --known-distance.
            if all(socket in connected for socket in STEREO_SOCKETS):
                sockets = STEREO_SOCKETS
            elif dai.CameraBoardSocket.CAM_A in connected:
                sockets = (dai.CameraBoardSocket.CAM_A,)
            else:
                raise RuntimeError(
                    f"Device {device_id} needs CAM_A or CAM_B/CAM_C; connected: {connected}"
                )
            print(f"Calibrating {device_id} with {', '.join(s.name for s in sockets)}")
            for socket in sockets:
                camera = pipeline.create(dai.node.Camera, device).build(
                    socket, sensorFps=CALIBRATION_FPS
                )
                calibration.addCamera(
                    camera.requestFullResolutionOutput(fps=CALIBRATION_FPS)
                )
            first_cameras.append((device_id, sockets[0]))

        if known_distance is not None:
            (id_a, socket_a), (id_b, socket_b) = first_cameras[:2]
            calibration.setKnownDistance(
                id_a,
                socket_a,
                id_b,
                socket_b,
                known_distance,
                dai.LengthUnit.CENTIMETER,
            )

        control_queue = calibration.inputControl.createInputQueue()
        result_queue = calibration.calibrationOutput.createOutputQueue()
        pipeline.start()
        print(
            f"Collecting {sample_count} synchronized samples. "
            "Point the cameras at a shared textured scene and keep them still."
        )
        control_queue.send(dai.beta.MultiDeviceCalibrationControl.start())
        result = result_queue.get(timedelta(minutes=3))

    if result is None:
        raise RuntimeError("Calibration timed out")
    if not result.passed or result.graph is None:
        raise RuntimeError(f"Calibration failed: {result.info}")
    if not result.getHandler().toJsonFile(output):
        raise RuntimeError(f"Failed to save calibration to {output}")
    print(f"Calibration saved to {output}")
    print(
        f"Confidence: {result.dataConfidence:.3f}, Sampson error: {result.sampsonError:.4g}"
    )


def load_or_calibrate(
    args, device_infos: List[dai.DeviceInfo]
) -> dai.beta.MultiDeviceCalibrationHandler:
    """Calibrate on the first run (or with --calibrate), then load the saved calibration."""
    if args.calibrate or not args.calibration.exists():
        calibrate(
            device_infos, args.calibration, args.sample_count, args.known_distance
        )
    else:
        print(f"Using calibration {args.calibration}; pass --calibrate to redo it")
    return dai.beta.MultiDeviceCalibrationHandler(args.calibration)
