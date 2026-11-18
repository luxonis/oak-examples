# AGENTS.md

## Summary

This is the repository reference for fusing spatial detections from multiple calibrated OAK devices into a single bird’s-eye view. Use it when you need multi-device 3D perception in one coordinate system rather than per-device outputs.

## Use This Example When

- You need multi-device 3D detection fusion.
- You already have a calibration file from [tutorials/multiple-devices/multi-device-calibration](https://github.com/luxonis/oak-examples/tree/main/tutorials/multiple-devices/multi-device-calibration).
- You want the repo’s most direct Bird’s Eye View fusion example.

## Do Not Use This Example When

- You do not have a multi-device calibration file yet.
- You need image stitching instead of 3D fusion.
- You need a standalone packaged deployment.

## Quick Facts

- `Category:` `tutorials/multiple-devices/spatial-detection-fusion`
- `Shape:` `multi-device-host`
- `Primary task:` fuse multi-camera spatial detections into a shared BEV visualization
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` none
- `Frontend:` none
- `Runs on:` host mode only, with two or more calibrated stereo-capable devices in one pipeline
- `Requires:` a `calibration.json` from the multi-device-calibration example, stereo-capable cameras, and host-side SciPy/NumPy dependencies
- `Input:` live `CAM_A/B/C` per device
- `Output:` per-device passthrough/detections plus `BEV Canvas`, `BEV Cameras`, `BEV History Trails`, and `BEV Detections`
- `Models:` fixed model slug in [utils/config.py](utils/config.py)
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [utils/config.py](utils/config.py)
- [utils/fusion.py](utils/fusion.py)
- [utils/birds_eye_view.py](utils/birds_eye_view.py)
- [utils/arguments.py](utils/arguments.py)

## Architecture

- [main.py](main.py) builds one `dai.Pipeline(createImplicitDevice=False)`, loads the calibration with `MultiDeviceCalibrationHandler` and applies it with `pipeline.setMultiDeviceCalibration`.
- Each device runs a `SpatialDetectionNetwork` created with `pipeline.create(node, device)`; a host `Sync` node groups one `SpatialImgDetections` per device.
- [utils/fusion.py](utils/fusion.py) moves every message into the first device's camera frame with `SpatialImgDetections.transformTo`, groups nearby detections of the same label, and prunes duplicates per camera.
- [utils/birds_eye_view.py](utils/birds_eye_view.py) renders the fused results, camera poses, and history trails into BEV annotation topics.

## Constraints

- Every selected device must be part of the calibration file; without `--devices` all calibrated devices are used.
- This example depends on the multi-device calibration workflow; moving cameras after calibration invalidates the fusion geometry.
- The first device's camera frame is the fusion and BEV coordinate system, so that device should be mounted roughly level.
- `BEV_LABELS` in [utils/config.py](utils/config.py) is empty by default, which means all labels are shown.
- The multi-device pipeline and calibration APIs require `depthai>=3.12`.

## Related Examples

- [tutorials/multiple-devices/multi-device-calibration](https://github.com/luxonis/oak-examples/tree/main/tutorials/multiple-devices/multi-device-calibration): run this first to create the required calibration file
- [tutorials/multiple-devices/multiple-devices-preview](https://github.com/luxonis/oak-examples/tree/main/tutorials/multiple-devices/multiple-devices-preview): use this when you only need independent streams per device
- [neural-networks/object-detection/spatial-detections](https://github.com/luxonis/oak-examples/tree/main/neural-networks/object-detection/spatial-detections): use this when you need the single-device spatial-detection baseline
- [tutorials/multiple-devices/multi-device-point-cloud](https://github.com/luxonis/oak-examples/tree/main/tutorials/multiple-devices/multi-device-point-cloud): merged 3D point cloud of calibrated devices
- [tutorials/multiple-devices/multi-device-panorama](https://github.com/luxonis/oak-examples/tree/main/tutorials/multiple-devices/multi-device-panorama): calibrated panorama of all devices
- [tutorials/multiple-devices/multi-device-birds-eye-view](https://github.com/luxonis/oak-examples/tree/main/tutorials/multiple-devices/multi-device-birds-eye-view): top-down ground view of calibrated devices

## Validation

- `Run:` `python3 main.py`
- `Success looks like:` the Visualizer shows per-device detection streams plus the BEV topics, and an object seen by several cameras appears as one group
- `Common failure meaning:` the calibration file is missing or stale, a selected device is not in the calibration, the devices are not stereo-capable, or the user expects a standalone or stitching-based solution instead of 3D fusion
