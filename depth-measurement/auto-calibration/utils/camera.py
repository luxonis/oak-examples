import depthai as dai


def select_stereo_resolution(features):
    """Select matching native sensor modes supported by AutoCalibration 3.11."""
    cameras = {feature.socket: feature for feature in features}
    pair = (dai.CameraBoardSocket.CAM_B, dai.CameraBoardSocket.CAM_C)
    if any(socket not in cameras for socket in pair):
        raise ValueError("AutoCalibration requires stereo cameras on CAM_B and CAM_C.")

    for size in ((1280, 800), (640, 400)):
        if all(
            size
            in {(config.width, config.height) for config in cameras[socket].configs}
            for socket in pair
        ):
            return size
    raise ValueError(
        "AutoCalibration requires matching native 1280x800 or 640x400 sensor modes "
        "on CAM_B/C. Other sensor modes need a separate calibration workflow."
    )
