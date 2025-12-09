KNOWN_FAILING = {
    "apps/focused-vision": {
        "reason": "RVC4 only app",
        "rules": {"and": [{"platform": ["rvc2"]}]},
    },
    "apps/people-demographics-and-sentiment-analysis": {
        "reason": "Not supported for peripheral; RVC4 only app",
        "rules": {
            "and": [
                {"mode": ["peripheral"]},
                {"platform": ["rvc2"]},
            ],
        },
    },
    "apps/ros/ros-driver-basic": {
        "reason": "Needs ros base image",
        "rules": {"and": [{"mode": ["peripheral"]}]},
    },
    "apps/ros/ros-driver-custom-workspace": {
        "reason": "Needs ros base image",
        "rules": {"and": [{"mode": ["peripheral"]}]},
    },
    "apps/ros/ros-driver-rgb-pcl": {
        "reason": "Needs ros base image",
        "rules": {"and": [{"mode": ["peripheral"]}]},
    },
    "apps/ros/ros-driver-spatial-bb": {
        "reason": "Needs ros base image",
        "rules": {"and": [{"mode": ["peripheral"]}]},
    },
    "tutorials/multiple-devices/multi-cam-calibration": {
        "reason": "Needs --include-ip flag turned to work on RVC4.",
        "rules": {"and": [{"platform": ["rvc4"]}]},
    },
    "tutorials/multiple-devices/multiple-devices-preview": {
        "reason": "Needs --include-ip flag turned to work on RVC4.",
        "rules": {"and": [{"platform": ["rvc4"]}]},
    },
    "tutorials/multiple-devices/spatial-detection-fusion": {
        "reason": "Not ported to latest DAI yet",
        "rules": {"and": [{"platform": "all"}]},
    },
    "tutorials/multiple-devices/multiple-device-stitch-nn": {
        "reason": "Test suite doesn't support multi-device testing",
        "rules": {"and": [{"platform": "all"}]},
    },
    "custom-frontend/raw-stream": {
        "reason": "Failed to start the HTTP server on peripheral.",
        "rules": {"and": [{"mode": "all"}]},
    },
    "custom-frontend/open-vocabulary-object-detection": {
        "reason": "Not supported for peripheral",
        "rules": {"and": [{"mode": ["peripheral"]}]},
    },
    "integrations/foxglove": {
        "reason": "No matching distribution found for open3d~=0.18 on Windows",
        "rules": {"and": [{"os": ["win"]}]},
    },
    "integrations/rerun": {
        "reason": "No matching distribution found for rerun-sdk==0.15.1 on Windows",
        "rules": {"and": [{"os": ["win"]}]},
    },
    "apps/data-collection": {
        "reason": "Not supported for peripheral; RVC4 only app",
        "rules": {
            "and": [
                {"mode": ["peripheral"]},
                {"platform": ["rvc2"]},
            ],
        },
    },
    "integrations/roboflow-dataset": {
        "reason": "Can't run without arguments (e.g. roboflow api-key)",
        "rules": {"and": [{"platform": "all"}]},
    },
    "integrations/roboflow-workflow": {
        "reason": "Can't run without arguments Roboflow arguments",
        "mode": "all",
        "platform": "all",
    },
    "neural-networks/speech-recognition/whisper-tiny-en": {
        "reason": "Complex example, works only on RVC4",
        "rules": {"and": [{"platform": ["rvc2"]}]},
    },
    "neural-networks/object-detection/yolo-world": {
        "reason": "Complex example, works only on RVC4",
        "rules": {"and": [{"platform": ["rvc2"]}]},
    },
    "neural-networks/ocr/license-plate-recognition": {
        "reason": "Complex example, works only on RVC4",
        "rules": {"and": [{"platform": ["rvc2"]}]},
    },
    "neural-networks/object-detection/thermal-detection": {
        "reason": "Needs thermal camera",
        "rules": {"and": [{"platform": "all"}]},
    },
    "neural-networks/depth-estimation/foundation-stereo": {
        "reason": "Requires a lot of host compute to run. No matching distribution found for onnxruntime-gpu>=1.19.0 for MacOS",
        "rules": {"or": [{"mode": ["standalone"]}, {"os": ["mac"]}]},
    },
    "integrations/hub-snaps-events": {
        "reason": "Missing token, please set DEPTHAI_HUB_API_KEY environment variable or use setToken method",
        "rules": {"and": [{"platform": "all"}]},
    },
    "depth-measurement/3d-measurement/tof-pointcloud": {
        "reason": "ToF cameras are only of the RVC2 variant",
        "rules": {"and": [{"platform": ["rvc4"]}]},
    },
    "depth-measurement/triangulation": {
        "reason": "Can't sync outputs inside Triangulation node",
        "rules": {"and": [{"platform": ["rvc4"]}]},
    },
    "depth-measurement/3d-measurement/box-measurement": {
        "reason": "No matching distribution found for open3d~=0.18 on Windows",
        "rules": {"and": [{"os": ["win"]}]},
    },
    "streaming/on-device-encoding": {
        "reason": "Cannot open include file: 'libavutil/mathematics.h'",
        "rules": {"and": [{"os": ["win"]}]},
    },
    "streaming/webrtc-streaming": {
        "reason": "Cannot open include file: 'libavutil/mathematics.h'",
        "rules": {"and": [{"os": ["win"]}]},
    },
    "streaming/rtsp-streaming": {
        "reason": "PyCairo installation issues",
        "rules": {"and": [{"platform": "all"}]},
    },
    "streaming/poe-mqtt": {
        "reason": "Needs backend connection sometimes, flaky to test.",
        "rules": {"and": [{"platform": "all"}]},
    },
    "tutorials/qr-with-tiling": {
        "reason": "Missing bindings for RVC2 in Script node. Missing `libzbar-64.dll` module on Windows and MacOS",
        "rules": {"or": [{"platform": ["rvc2"]}, {"os": ["win", "mac"]}]},
    },
    "tutorials/play-encoded-stream": {
        "reason": "Missing bindings for RVC2 in Script node. Cannot open include file for Windows",
        "rules": {"or": [{"platform": ["rvc2"]}, {"os": ["win"]}]},
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
