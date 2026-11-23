"""Device and stored IMU calibration summary for the frontend's device panel."""

from typing import List, Optional

import depthai as dai
import numpy as np

from utils.board_config import ImuMounting

_DEFAULT_CALIBRATION = np.hstack([np.eye(3), np.zeros((3, 1))])


def has_magnetometer(imu_name: str) -> bool:
    # BMI270 (RVC2) has no magnetometer; BNO086 (RVC2) and the RVC4 IMU ("accel") do.
    return not imu_name.startswith("BMI")


def read_device_info(device: dai.Device, mounting: ImuMounting) -> dict:
    calibration = device.readCalibration2()
    eeprom = calibration.getEepromData()
    imu = device.getConnectedIMU()
    rotation = eeprom.imuExtrinsics.rotationMatrix or None
    accelerometer = calibration.getAccelerometerCalibration() or None
    gyroscope = calibration.getGyroscopeCalibration() or None
    return {
        "name": device.getDeviceName(),
        "id": device.getDeviceId(),
        "platform": device.getPlatformAsString(),
        "productName": eeprom.productName,
        "boardName": eeprom.boardName,
        "boardRev": eeprom.boardRev,
        "imu": imu,
        "imuFirmware": str(device.getIMUFirmwareVersion()),
        "magnetometer": has_magnetometer(imu),
        "extrinsics": "flashed" if rotation else "missing",
        "accelerometer": _status(accelerometer),
        "gyroscope": _status(gyroscope),
        "socket": mounting.socket.name,
        "translationCm": [float(v) for v in mounting.translation_cm],
        "mountingSource": mounting.source,
        # Stored values; the frontend applies them to RAW samples to draw the "old" calibration.
        "calibration": {
            "rotation": rotation,
            "accelerometer": accelerometer,
            "gyroscope": gyroscope,
        },
    }


def _status(matrix: Optional[List[List[float]]]) -> str:
    if not matrix:
        return "missing"
    return "default" if np.allclose(matrix, _DEFAULT_CALIBRATION) else "calibrated"
