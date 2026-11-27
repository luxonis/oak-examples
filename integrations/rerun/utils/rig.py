import http.client
import logging
import urllib.request
from pathlib import Path

import depthai as dai
import numpy as np
import rerun as rr

logger = logging.getLogger(__name__)

MESH_URL = "https://raw.githubusercontent.com/luxonis/depthai-ros/be24f1c762281ccbfde163bd4288ada4236b406c/depthai_descriptions/urdf/models/{model}.stl"
MESH_MODELS = {
    "OAK-1",
    "OAK-D",
    "OAK-D-CM4-POE",
    "OAK-D-IOT-75",
    "OAK-D-LITE",
    "OAK-D-LR",
    "OAK-D-POE",
    "OAK-D-PRO",
    "OAK-D-PRO-W",
    "OAK-D-S2",
    "OAK-D-S2-POE",
    "OAK-D-SR",
    "OAK-D-SR-POE",
    "OAK-T",
    "OAK4-D",
    "OAK4-S",
}
MESH_ALIASES = {
    "OAK-4-D": "OAK4-D",
    "OAK-4-PRO": "OAK4-D",
    "OAK-4-PRO-W": "OAK4-D",
    "OAK-4-S": "OAK4-S",
    "OAK-D-PRO-POE": "OAK-D-S2-POE",
    "OAK-D-PRO-W-POE": "OAK-D-S2-POE",
    "OAK-D-W": "OAK-D-S2",
    "OAK4-D-PRO": "OAK4-D",
    "OAK4-D-W": "OAK4-D",
}
MESH_ANCHORS = {
    "OAK-D-PRO-W": (dai.CameraBoardSocket.CAM_A, [0.0485, 0.0195, -0.0228]),
    "OAK-D-SR": (dai.CameraBoardSocket.CAM_C, [-0.01, 0.0, 0.0]),
    "OAK-D-SR-POE": (dai.CameraBoardSocket.CAM_A, [-0.019, 0.0, 0.0]),
    "OAK-T": (dai.CameraBoardSocket.CAM_E, [-0.025, 0.0, 0.0]),
}
MESH_CACHE_DIR = Path.home() / ".cache" / "oak-examples" / "meshes"
MESH_DOWNLOAD_TIMEOUT_S = 10
RDF_FROM_LUF = np.diag([-1.0, -1.0, 1.0])

CM_PER_M = 100.0
IMU_AXES_LENGTH_M = 0.02


def log_rig(
    device: dai.Device,
    calibration: dai.CalibrationHandler,
    camera_names: dict[dai.CameraBoardSocket, str],
) -> str | None:
    model = device.getDeviceName()
    rr.send_recording_name(model)
    rr.send_property(
        "device",
        rr.AnyValues(
            product=device.getProductName(),
            device_id=device.getDeviceId(),
            platform=device.getPlatformAsString(),
            imu=device.getConnectedIMU(),
        ),
    )

    rr.log("oak", rr.ViewCoordinates.RDF, static=True)
    calibrated = calibration.getEepromData().cameraData
    for socket, name in camera_names.items():
        if socket not in calibrated:
            logger.warning(
                f"{socket.name} is not calibrated, showing it at the origin."
            )
            continue
        origin_from_camera_cm, _ = calibration.getExtrinsicsToOrigin(socket)
        origin_from_camera = np.array(origin_from_camera_cm)
        rr.log(
            f"oak/{name}",
            rr.Transform3D(
                translation=origin_from_camera[:3, 3] / CM_PER_M,
                mat3x3=origin_from_camera[:3, :3],
            ),
            static=True,
        )

    _log_mesh(MESH_ALIASES.get(model, model), camera_names)
    return _log_imu_frame(calibration, camera_names)


def _log_imu_frame(
    calibration: dai.CalibrationHandler, camera_names: dict[dai.CameraBoardSocket, str]
) -> str | None:
    eeprom = calibration.getEepromData()
    imu_camera = eeprom.imuExtrinsics.toCameraSocket
    if imu_camera not in camera_names or imu_camera not in eeprom.cameraData:
        return None
    camera_from_imu = np.array(
        calibration.getImuToCameraExtrinsics(imu_camera, unit=dai.LengthUnit.METER)
    )
    entity_path = f"oak/{camera_names[imu_camera]}/imu"
    rr.log(
        entity_path,
        rr.Transform3D(translation=camera_from_imu[:3, 3]),
        rr.TransformAxes3D(IMU_AXES_LENGTH_M),
        static=True,
    )
    return entity_path


def _log_mesh(model: str, camera_names: dict[dai.CameraBoardSocket, str]) -> None:
    reference_camera, mesh_offset_m = MESH_ANCHORS.get(
        model, (dai.CameraBoardSocket.CAM_A, [0.0, 0.0, 0.0])
    )
    if model not in MESH_MODELS or reference_camera not in camera_names:
        logger.info(f"No housing mesh for '{model}', showing the cameras only.")
        return
    path = MESH_CACHE_DIR / f"{model}.stl"
    if not path.exists():
        logger.info(f"Downloading the {model} housing mesh...")
        try:
            with urllib.request.urlopen(
                MESH_URL.format(model=model), timeout=MESH_DOWNLOAD_TIMEOUT_S
            ) as response:
                mesh = response.read()
        except (OSError, http.client.HTTPException) as err:
            logger.warning(
                f"Could not download the housing mesh, showing the cameras only: {err}"
            )
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        partial_path = path.with_suffix(".part")
        partial_path.write_bytes(mesh)
        partial_path.replace(path)
    rr.log(
        f"oak/{camera_names[reference_camera]}/model",
        rr.Asset3D(path=path),
        rr.Transform3D(translation=mesh_offset_m, mat3x3=RDF_FROM_LUF),
        static=True,
    )
