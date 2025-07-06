# Dict of known failing examples:
# key: example path
# value: Dict of conditions under which it is failing
#     reason (str): Reason why example is failing under this conditions
#     mode ("all" | List[Literal["peripheral", "standalone"]]): In which mode is it failing
#     platform ("all" | List[Literal["rvc2", "rvc4"]]): On which platform is it failing
#     python_version ("all" | List[Literal["3.8", "3.10", "3.12"]]): On which python version is it failing
#     dai_version ("all" | str): On which dai version is it failing. Can be e.g. >3.0.0rc1, <=3.0.0a14, etc. Supported ops: <,>,<=,>=

KNOWN_FAILING = {
    "tutorials/multiple-devices/multi-cam-calibration": {
        "reason": "Not ported to latest DAI yet",
        "mode": "all",
        "platform": "all",
    },
    "tutorials/multiple-devices/spatial-detection-fusion": {
        "reason": "Not ported to latest DAI yet",
        "mode": "all",
        "platform": "all",
    },
    "tutorials/multiple-devices/multiple-devices-preview": {
        "reason": "Needs multiple devices",
        "mode": "all",
        "platform": "all",
    },
    "custom-frontend/raw-stream": {
        "reason": "Failed to start the HTTP server",
        "mode": "all",
        "platform": "all",
    },
    "integrations/roboflow-integration": {
        "reason": "Can't run without arguments (e.g. roboflow api-key)",
        "mode": "all",
        "platform": "all",
    },
    "neural-networks/speech-recognition/whisper-tiny-en": {
        "reason": "Complex example, needs to be updated",
        "mode": "all",
        "platform": "all",
    },
    "neural-networks/object-detection/yolo-world": {
        "reason": "Complex example, works only on RVC4",
        "mode": "all",
        "platform": ["rvc2"],
    },
    "neural-networks/ocr/license-plate-recognition": {
        "reason": "Complex example, works only on RVC4",
        "mode": "all",
        "platform": ["rvc2"],
    },
    "neural-networks/object-detection/thermal-detection": {
        "reason": "Needs thermal camera",
        "mode": "all",
        "platform": "all",
    },
    "neural-networks/object-tracking/kalman": {
        "reason": "Pipeline node with name: 'ObjectTracker' doesn't exist",
        "mode": "all",
        "platform": ["rvc4"],
    },
    "neural-networks/object-tracking/collision-avoidance": {
        "reason": "Pipeline node with name: 'ObjectTracker' doesn't exist",
        "mode": "all",
        "platform": ["rvc4"],
    },
    "neural-networks/object-tracking/people-tracker": {
        "reason": "Pipeline node with name: 'ObjectTracker' doesn't exist",
        "mode": "all",
        "platform": ["rvc4"],
    },
    "neural-networks/counting/cumulative-object-counting": {
        "reason": "Pipeline node with name: 'ObjectTracker' doesn't exist",
        "mode": "all",
        "platform": ["rvc4"],
    },
    "neural-networks/counting/depth-people-counting": {
        "reason": "Pipeline node with name: 'ObjectTracker' doesn't exist",
        "mode": "all",
        "platform": ["rvc4"],
    },
    "integrations/rerun": {
        "reason": "Failed loading `libxkbcommon-x11.so.0",
        "mode": "all",
        "platform": ["rvc4"],
    },
    "integrations/foxglove": {
        "reason": "Loaded model is for RVC2, but the device is RVC4",
        "mode": "all",
        "platform": ["rvc4"],
    },
    "integrations/hub-snaps-events": {
        "reason": "Missing token, please set DEPTHAI_HUB_API_KEY environment variable or use setToken method - Needs to be set by the user.",
        "mode": "all",
        "platform": "all",
    },
    "depth-measurement/3d-measurement/box-measurement": {
        "reason": "Open3D causes some memory segfault",
        "mode": "all",
        "platform": "all",
    },
    "depth-measurement/triangulation": {
        "reason": "Can't sync outputs inside Triangulation node",
        "mode": "all",
        "platform": ["rvc4"],
    },
    "streaming/rtsp-streaming": {
        "reason": "PyCairo installation issues",
        "mode": "all",
        "platform": "all",
    },
    "streaming/poe-mqtt": {
        "reason": "Needs backend connection sometimes, flaky to test.",
        "mode": "all",
        "platform": "all",
    },
}

IGNORED_WARNINGS = [
    "The issued warnings are orientative, based on optimal settings for a single network, if multiple networks are running in parallel the optimal settings may vary",
    "Did not get the input image sizes from the imageIn input. Defaulting to 416 x 416",
    "Network compiled for 8 shaves, maximum available",
    "UserWarning: Specified provider 'TensorrtExecutionProvider' is not in available",
    "UserWarning: Specified provider 'CUDAExecutionProvider' is not in available",
    "You are using ImgDetectionsBridge to transform from ImgDetectionsExtended to ImgDetections.",
    "Sync node has been trying to sync for",
]
