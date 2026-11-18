# AGENTS.md

## Summary

This is the repository reference for composing a calibrated panorama from multiple OAK devices with the native Stitching node. Use it when you need one wide image from several devices without feature matching.

## Use This Example When

- You need one wide image from the color cameras of several devices.
- You want the minimal calibrated `Stitching` `PANORAMA` pipeline.
- You want calibration and the application in one script that runs a single pipeline across all devices.

## Do Not Use This Example When

- You need detections on the panorama; use [multiple-device-stitch-nn](https://github.com/luxonis/oak-examples/tree/main/tutorials/multiple-devices/multiple-device-stitch-nn).
- You only have one device.
- You need a packaged standalone app.

## Quick Facts

- `Category:` `tutorials/multiple-devices/multi-device-panorama`
- `Shape:` `multi-device-host`
- `Primary task:` calibrate multiple devices and stitch their cameras into a panorama
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` none
- `Frontend:` none
- `Runs on:` host mode only, with two or more DepthAI devices in one pipeline
- `Requires:` two or more devices that see a shared textured scene during calibration
- `Input:` live undistorted `CAM_A` `1280x800` NV12 per device
- `Output:` `Input - <device id>` topics and a `Panorama` topic
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
- Each device sends one undistorted NV12 view; calibrated composition needs undistorted inputs.
- One host `Stitching` node in `PANORAMA` mode with `setUseInputCalibration(True)` renders the views with the camera model selected by `--projection`.

## Constraints

- At least two devices are required; moving a device invalidates `calibration.json` until `--calibrate` is run.
- The metric scale comes from a `CAM_B`/`CAM_C` stereo pair or from `--known-distance`.
- The devices are not hardware-synchronized; frames are grouped within one frame period.
- Near objects show parallax at the seams because the devices do not share an optical center.
- The multi-device pipeline and calibration APIs require `depthai>=3.12`.

## Related Examples

- [tutorials/multiple-devices/multi-device-calibration](https://github.com/luxonis/oak-examples/tree/main/tutorials/multiple-devices/multi-device-calibration): use this when you only need the calibration file
- [tutorials/multiple-devices/multi-device-point-cloud](https://github.com/luxonis/oak-examples/tree/main/tutorials/multiple-devices/multi-device-point-cloud): merged 3D point cloud of all devices
- [tutorials/multiple-devices/multi-device-panorama](https://github.com/luxonis/oak-examples/tree/main/tutorials/multiple-devices/multi-device-panorama): calibrated panorama of all devices
- [tutorials/multiple-devices/multi-device-birds-eye-view](https://github.com/luxonis/oak-examples/tree/main/tutorials/multiple-devices/multi-device-birds-eye-view): top-down ground view of all devices

## Validation

- `Run:` `python3 main.py --devices <id-or-ip> <id-or-ip>`
- `Success looks like:` the Visualizer shows one panorama in which distant scenery is continuous across the seams
- `Common failure meaning:` the calibration failed or is stale (broken geometry everywhere), or only near objects are misaligned, which is parallax and expected
