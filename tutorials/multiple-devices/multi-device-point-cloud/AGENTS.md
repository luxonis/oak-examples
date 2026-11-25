# AGENTS.md

## Summary

This is the repository reference for merging the depth of multiple calibrated OAK devices into one point cloud with a single PointCloud node. Use it when you need a common 3D reconstruction from several devices.

## Use This Example When

- You need one point cloud built from several stereo devices.
- You want to see the multi-stream `PointCloud` node fed from different devices.
- You want calibration and the application in one script that runs a single pipeline across all devices.

## Do Not Use This Example When

- You need a point cloud from a single device; use the single-device point cloud examples.
- You only have one device.
- You need a packaged standalone app.

## Quick Facts

- `Category:` `tutorials/multiple-devices/multi-device-point-cloud`
- `Shape:` `multi-device-host`
- `Primary task:` calibrate multiple devices and merge their depth into one colored point cloud
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` none
- `Frontend:` none
- `Runs on:` host mode only, with two or more DepthAI devices in one pipeline
- `Requires:` two or more stereo-capable devices that see a shared textured scene
- `Input:` live `CAM_A` color and stereo depth per device
- `Output:` `Color - <device id>` topics and a `Merged point cloud` 3D topic
- `Models:` none
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [utils/calibration.py](utils/calibration.py)
- [utils/arguments.py](utils/arguments.py)

## Architecture

- [utils/calibration.py](utils/calibration.py) runs `dai.beta.node.MultiDeviceCalibration` in its own pipeline on the first run and saves `calibration.json`; later runs load it with `MultiDeviceCalibrationHandler`.
- [main.py](main.py) builds one `dai.Pipeline(createImplicitDevice=False)`, applies the calibration with `pipeline.setMultiDeviceCalibration` and creates the per-device nodes with `pipeline.create(node, device)`.
- Each device contributes an undistorted `640x400` RGB output and a `Depth` node aligned to it.
- One host `PointCloud` node receives the streams through `getDepthInput(device_id)` and `getColorInput(device_id)` and publishes one cloud in meters in the calibration origin frame.

## Constraints

- At least two devices are required; moving a device invalidates `calibration.json` until `--calibrate` is run.
- The metric scale comes from a `CAM_B`/`CAM_C` stereo pair or from `--known-distance`.
- The devices are not hardware-synchronized; frames are grouped within one frame period.
- Every device needs a stereo pair for depth.
- The multi-device pipeline and calibration APIs require `depthai>=3.12`.

## Related Examples

- [tutorials/multiple-devices/multi-device-calibration](https://github.com/luxonis/oak-examples/tree/main/tutorials/multiple-devices/multi-device-calibration): use this when you only need the calibration file
- [tutorials/multiple-devices/multiple-device-stitch-nn](https://github.com/luxonis/oak-examples/tree/main/tutorials/multiple-devices/multiple-device-stitch-nn): calibrated panorama of all devices with merged detections
- [tutorials/multiple-devices/multi-device-birds-eye-view](https://github.com/luxonis/oak-examples/tree/main/tutorials/multiple-devices/multi-device-birds-eye-view): top-down ground view of all devices
- [tutorials/multiple-devices/spatial-detection-fusion](https://github.com/luxonis/oak-examples/tree/main/tutorials/multiple-devices/spatial-detection-fusion): fused 3D detections from calibrated devices

## Validation

- `Run:` `python3 main.py --devices <id-or-ip> <id-or-ip>`
- `Success looks like:` the Visualizer shows one coherent colored point cloud and objects in the overlap are not doubled
- `Common failure meaning:` the calibration failed or is stale (doubled objects), a device has no stereo pair, or the network cannot carry all streams (lower `--fps_limit`)
