# AGENTS.md

## Summary

This is the repository reference for a multi-device bird's-eye view: the ground plane is fitted to the merged point cloud of calibrated OAK devices and the Stitching node projects all cameras onto it. Use it for a metric top-down floor view.

## Use This Example When

- You need a top-down view of the floor composed from several devices.
- You want to see a plane fitted to a merged point cloud drive `Stitching` `PLANAR_PROJECTION`.
- You want calibration and the application in one script that runs a single pipeline across all devices.

## Do Not Use This Example When

- You need a bird's-eye view of detections instead of images; use [spatial-detection-fusion](https://github.com/luxonis/oak-examples/tree/main/tutorials/multiple-devices/spatial-detection-fusion).
- You only have one device.
- You need a packaged standalone app.

## Quick Facts

- `Category:` `tutorials/multiple-devices/multi-device-birds-eye-view`
- `Shape:` `multi-device-host`
- `Primary task:` calibrate multiple devices, fit the ground plane and project the cameras onto it
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` none
- `Frontend:` none
- `Runs on:` host mode only, with two or more DepthAI devices in one pipeline
- `Requires:` two or more stereo-capable devices that see the floor, mounted roughly upright, plus host-side NumPy
- `Input:` stereo depth per device for the plane fit, then live full-resolution `CAM_A` NV12 per device
- `Output:` the fitted plane in the terminal, `Input - <device id>` topics and a `Birds-eye view` topic
- `Models:` none
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [utils/calibration.py](utils/calibration.py)
- [utils/plane.py](utils/plane.py)
- [utils/arguments.py](utils/arguments.py)

## Architecture

- [utils/calibration.py](utils/calibration.py) runs `dai.beta.node.MultiDeviceCalibration` in its own pipeline on the first run and saves `calibration.json`; later runs load it with `MultiDeviceCalibrationHandler`.
- [main.py](main.py) builds one `dai.Pipeline(createImplicitDevice=False)`, applies the calibration with `pipeline.setMultiDeviceCalibration` and creates the per-device nodes with `pipeline.create(node, device)`.
- `estimate_ground_plane` runs a first pipeline with one `Depth` per device and a host `PointCloud` node, then [utils/plane.py](utils/plane.py) fits the ground with RANSAC.
- The second pipeline feeds `requestFullResolutionOutput` frames of every device into a host `Stitching` node in `PLANAR_PROJECTION` mode configured with `setPlane` and `setMaxRange`; a separate `640x400` preview goes to the Visualizer.

## Constraints

- At least two devices are required; moving a device invalidates `calibration.json` until `--calibrate` is run.
- The metric scale comes from a `CAM_B`/`CAM_C` stereo pair or from `--known-distance`.
- The devices are not hardware-synchronized; frames are grouped within one frame period.
- The projection inputs must come from `requestFullResolutionOutput`: on depthai 3.12 a `requestOutput` with an explicit size makes the node report that no input sees the plane. Full-resolution frames limit the rate to about 5 FPS.
- The multi-device pipeline and calibration APIs require `depthai>=3.12`.

## Related Examples

- [tutorials/multiple-devices/multi-device-calibration](https://github.com/luxonis/oak-examples/tree/main/tutorials/multiple-devices/multi-device-calibration): use this when you only need the calibration file
- [tutorials/multiple-devices/multi-device-point-cloud](https://github.com/luxonis/oak-examples/tree/main/tutorials/multiple-devices/multi-device-point-cloud): merged 3D point cloud of all devices
- [tutorials/multiple-devices/multi-device-panorama](https://github.com/luxonis/oak-examples/tree/main/tutorials/multiple-devices/multi-device-panorama): calibrated panorama of all devices
- [tutorials/multiple-devices/multi-device-birds-eye-view](https://github.com/luxonis/oak-examples/tree/main/tutorials/multiple-devices/multi-device-birds-eye-view): top-down ground view of all devices

## Validation

- `Run:` `python3 main.py --devices <id-or-ip> <id-or-ip>`
- `Success looks like:` the terminal reports a plausible camera height above the ground and the Visualizer shows a top-down floor view in which floor patterns keep their shape
- `Common failure meaning:` no roughly horizontal plane was found (floor not visible or cameras strongly tilted), the calibration is stale, or objects above the floor look smeared, which is expected
