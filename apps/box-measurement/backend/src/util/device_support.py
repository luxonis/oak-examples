import depthai as dai

_REQUIRED_SOCKETS = (
    dai.CameraBoardSocket.CAM_A,
    dai.CameraBoardSocket.CAM_B,
    dai.CameraBoardSocket.CAM_C,
)


class UnsupportedDeviceError(Exception):
    pass


def check_device_supported(device: dai.Device) -> None:
    cameras = device.getConnectedCameras()

    missing = [socket.name for socket in _REQUIRED_SOCKETS if socket not in cameras]
    if not missing:
        return

    raise UnsupportedDeviceError(
        f"This device cannot run the Box Measurement app: missing "
        f"{', '.join(missing)}. Box measurement needs a stereo camera pair to "
        f"compute depth, so it requires an OAK 4 D (Pro and non-Pro are both "
        f"supported)."
    )
