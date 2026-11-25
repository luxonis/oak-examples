"""IMU mounting (camera socket, translation, spec rotation) from luxonis/depthai-boards."""

import io
import json
import tarfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import depthai as dai
import numpy as np

BOARDS_ARCHIVE_URL = "https://codeload.github.com/luxonis/depthai-boards/tar.gz/main"


@dataclass(frozen=True)
class ImuMounting:
    socket: dai.CameraBoardSocket
    translation_cm: List[float]
    spec_translation_cm: List[float]
    spec_rotation: Optional[np.ndarray]  # None when depthai-boards was not available
    source: str


def resolve_mounting(
    calibration: dai.CalibrationHandler, imu_name: str, board_config: Optional[Path]
) -> ImuMounting:
    """Use the depthai-boards spec; fall back to the values already in EEPROM when it cannot be fetched."""
    eeprom = calibration.getEepromData()
    if board_config is not None:
        return _mounting_from_board(
            json.loads(board_config.read_text()), imu_name, board_config.name
        )
    try:
        board, name = _download_board_config(eeprom)
        return _mounting_from_board(board, imu_name, name)
    except (OSError, tarfile.TarError, LookupError, ValueError) as e:
        return _mounting_from_eeprom(
            eeprom, f"EEPROM (depthai-boards lookup failed: {e})"
        )


def _download_board_config(eeprom: dai.EepromData) -> Tuple[dict, str]:
    """Find the board config whose batch EEPROM entry matches this device's product and board name."""
    with urllib.request.urlopen(BOARDS_ARCHIVE_URL, timeout=10) as response:
        archive = tarfile.open(fileobj=io.BytesIO(response.read()))
    # Drop the "<repo>-<ref>/" prefix; only JSON members are read, nothing is extracted to disk.
    files = {
        m.name.split("/", 1)[1]: m
        for m in archive.getmembers()
        if m.isfile() and "/" in m.name
    }

    def read(path: str) -> dict:
        return json.load(archive.extractfile(files[path]))

    batches = [
        p
        for p in files
        if p.startswith("batch/") and p.count("/") == 1 and p.endswith(".json")
    ]
    for batch in batches:
        for variant in read(batch).get("variants", []):
            eeprom_path = f"batch/{variant.get('eeprom')}"
            config = variant.get("board_config_file")
            if config and eeprom_path in files:
                entry = read(eeprom_path)
                if (entry.get("productName"), entry.get("boardName")) == (
                    eeprom.productName,
                    eeprom.boardName,
                ):
                    return read(f"boards/{config}"), config
    raise LookupError(f"no entry for {eeprom.productName} ({eeprom.boardName})")


def _mounting_from_board(board: dict, imu_name: str, name: str) -> ImuMounting:
    sensors = list(board["board_config"]["imuExtrinsics"]["sensors"].values())
    if not sensors:
        raise LookupError(f"{name} has no IMU extrinsics")
    # RVC2 reports the chip (BNO086, BMI270) and boards list both options; RVC4 reports a generic
    # name ("accel"), and its boards list the accel/gyro chip first, before the magnetometer.
    sensor = next(
        (
            s
            for s in sensors
            if imu_name.startswith(s["name"]) or s["name"].startswith(imu_name)
        ),
        sensors[0],
    )
    extrinsics = sensor["extrinsics"]
    translation = [float(extrinsics["specTranslation"][axis]) for axis in "xyz"]
    return ImuMounting(
        socket=dai.CameraBoardSocket.__members__[extrinsics["to_cam"]],
        translation_cm=translation,
        spec_translation_cm=translation,
        spec_rotation=np.asarray(extrinsics["rotationMatrix"], dtype=float),
        source=f"depthai-boards {name}",
    )


def _mounting_from_eeprom(eeprom: dai.EepromData, source: str) -> ImuMounting:
    extrinsics = eeprom.imuExtrinsics
    socket = extrinsics.toCameraSocket
    if socket == dai.CameraBoardSocket.AUTO:
        socket = dai.CameraBoardSocket.CAM_A
    return ImuMounting(
        socket=socket,
        translation_cm=[
            extrinsics.translation.x,
            extrinsics.translation.y,
            extrinsics.translation.z,
        ],
        spec_translation_cm=[
            extrinsics.specTranslation.x,
            extrinsics.specTranslation.y,
            extrinsics.specTranslation.z,
        ],
        spec_rotation=None,
        source=source,
    )
