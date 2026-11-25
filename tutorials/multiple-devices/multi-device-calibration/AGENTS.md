# AGENTS.md

## Summary

This is the repository reference for calibrating the relative poses of multiple OAK devices with the native MultiDeviceCalibration node. Use it when another multi-device example needs all devices in one coordinate system.

## Use This Example When

- You need one calibration file describing the poses of multiple devices.
- You want a target-free calibration that uses the scene the cameras share.
- You plan to use [tutorials/multiple-devices/spatial-detection-fusion](https://github.com/luxonis/oak-examples/tree/main/tutorials/multiple-devices/spatial-detection-fusion), [multi-device-point-cloud](https://github.com/luxonis/oak-examples/tree/main/tutorials/multiple-devices/multi-device-point-cloud), [multi-device-birds-eye-view](https://github.com/luxonis/oak-examples/tree/main/tutorials/multiple-devices/multi-device-birds-eye-view) or another example that calls `pipeline.setMultiDeviceCalibration`.

## Do Not Use This Example When

- You only need a preview of multiple devices.
- You need a packaged standalone app.
- You need intrinsic calibration or the stereo calibration of a single device.

## Quick Facts

- `Category:` `tutorials/multiple-devices/multi-device-calibration`
- `Shape:` `multi-device-host`
- `Primary task:` estimate cross-device extrinsics with `dai.beta.node.MultiDeviceCalibration`
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` none
- `Frontend:` none
- `Runs on:` host mode only, with two or more DepthAI devices in one pipeline
- `Requires:` a static textured scene visible to all devices; a stereo pair on at least one device or `--known-distance`
- `Input:` full-resolution `CAM_B`/`CAM_C` per stereo device, otherwise `CAM_A`
- `Output:` `calibration.json` written by `MultiDeviceCalibrationHandler` and camera previews in the Visualizer
- `Models:` none
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [utils/utility.py](utils/utility.py)
- [utils/arguments.py](utils/arguments.py)

## Architecture

- [main.py](main.py) builds one `dai.Pipeline(createImplicitDevice=False)`, adds every device with `pipeline.addDevice` and creates each `Camera` on its device with `pipeline.create(dai.node.Camera, device)`.
- Full-resolution camera outputs are registered with `MultiDeviceCalibration.addCamera`; a `640x400` preview of one camera per device goes to the Visualizer.
- Pressing `c` sends `MultiDeviceCalibrationControl.start()`; the result arrives on `calibrationOutput` and is saved with `result.getHandler().toJsonFile`.
- [utils/utility.py](utils/utility.py) resolves `--devices` or discovers devices, skipping IP-only devices unless `--include-ip` is set.

## Constraints

- At least two devices are required.
- The metric scale comes from a `CAM_B`/`CAM_C` stereo pair or from `--known-distance`, which applies to the first two devices.
- Poses are relative to an automatically selected origin device, not to a floor or world target.
- Moving a device after calibration invalidates the file.
- `MultiDeviceCalibration` lives in the `dai.beta` namespace and requires `depthai>=3.12`.

## Related Examples

- [tutorials/multiple-devices/spatial-detection-fusion](https://github.com/luxonis/oak-examples/tree/main/tutorials/multiple-devices/spatial-detection-fusion): use this after calibration when you need fused 3D detections
- [tutorials/multiple-devices/multi-device-preview](https://github.com/luxonis/oak-examples/tree/main/tutorials/multiple-devices/multi-device-preview): use this when you only need the multi-device pipeline without calibration
- [tutorials/multiple-devices/multi-device-stitch-nn](https://github.com/luxonis/oak-examples/tree/main/tutorials/multiple-devices/multi-device-stitch-nn): use this when multiple devices should be stitched into one panorama
- [tutorials/multiple-devices/multi-device-point-cloud](https://github.com/luxonis/oak-examples/tree/main/tutorials/multiple-devices/multi-device-point-cloud): merged 3D point cloud of calibrated devices
- [tutorials/multiple-devices/multi-device-birds-eye-view](https://github.com/luxonis/oak-examples/tree/main/tutorials/multiple-devices/multi-device-birds-eye-view): top-down ground view of calibrated devices

## Validation

- `Run:` `python3 main.py --devices <id-or-ip> <id-or-ip>`
- `Controls:` press `c` to calibrate and `q` to quit
- `Success looks like:` the terminal reports the confidence and per-device positions, and `calibration.json` appears
- `Common failure meaning:` the cameras do not share enough textured static scene, fewer than two devices were selected, or no stereo pair and no `--known-distance` was given
