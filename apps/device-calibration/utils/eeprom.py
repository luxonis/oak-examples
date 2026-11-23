"""Map a Rig to and from dai.CalibrationHandler. The only calibration module that imports depthai."""

from typing import Dict, Tuple

import depthai as dai
import numpy as np

from .camera_calibration import CameraCalib, Rig

_SPEC = ("x", "y", "z")


def _socket(name: str) -> dai.CameraBoardSocket:
    return getattr(dai.CameraBoardSocket, name)


def rig_from_handler(
    handler: dai.CalibrationHandler, board_cfg: dict, sizes: Dict[str, Tuple[int, int]]
) -> Rig:
    """Old calibration. Cameras (or links) without stored data are left out."""
    rig = Rig({}, {})
    for name, (w, h) in sizes.items():
        try:
            K = np.array(handler.getCameraIntrinsics(_socket(name), w, h))
            dist = np.array(handler.getDistortionCoefficients(_socket(name)))
            fisheye = handler.getDistortionModel(_socket(name)) == dai.CameraModel.Fisheye
        except RuntimeError:
            continue
        rig.cameras[name] = CameraCalib(K, dist[:4] if fisheye else dist,
                                        "fisheye" if fisheye else "perspective", (w, h))
    for name, cam in board_cfg["cameras"].items():
        to = cam.get("extrinsics", {}).get("to_cam")
        if name in rig.cameras and to in rig.cameras:
            try:
                rig.extrinsics[(name, to)] = np.array(
                    handler.getCameraExtrinsics(_socket(name), _socket(to)))
            except RuntimeError:
                pass
    stereo = board_cfg.get("stereo_config")
    if stereo and stereo["left_cam"] in rig.cameras and stereo["right_cam"] in rig.cameras:
        try:
            rig.rectification = (np.array(handler.getStereoLeftRectificationRotation()),
                                 np.array(handler.getStereoRightRectificationRotation()))
        except RuntimeError:
            pass
    return rig


def apply_rig(handler: dai.CalibrationHandler, rig: Rig, board_cfg: dict) -> None:
    cams = board_cfg["cameras"]
    for name, calib in rig.cameras.items():
        s = _socket(name)
        handler.setCameraIntrinsics(s, calib.K.tolist(), *calib.size)
        handler.setDistortionCoefficients(s, np.pad(calib.dist, (0, 14 - len(calib.dist))).tolist())
        handler.setFov(s, cams[name]["hfov"])
        if calib.model == "fisheye":
            handler.setCameraType(s, dai.CameraModel.Fisheye)
        if cams[name].get("hasAutofocus"):
            handler.setLensPosition(s, int(cams[name].get("lensPosition", 135)))
    for (src, dst), T in rig.extrinsics.items():
        spec = cams[src].get("extrinsics", {}).get("specTranslation", {})
        handler.setCameraExtrinsics(_socket(src), _socket(dst), T[:3, :3].tolist(), T[:3, 3].tolist(),
                                    [float(spec.get(a, 0.0)) for a in _SPEC])
    if rig.rectification is not None:
        stereo = board_cfg["stereo_config"]
        handler.setStereoLeft(_socket(stereo["left_cam"]), rig.rectification[0].tolist())
        handler.setStereoRight(_socket(stereo["right_cam"]), rig.rectification[1].tolist())
