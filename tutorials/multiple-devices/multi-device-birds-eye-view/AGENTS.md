# AGENTS.md

## Summary

This is the repository reference for a multi-device bird's-eye view: the ground plane is found in the origin device's point cloud with the depthai-nodes `AutoSupportPlane` node and the Stitching node projects all cameras onto it. Use it for a metric top-down floor view.

## Use This Example When

- You need a top-down view of the floor composed from several devices.
- You want to see an `AutoSupportPlane` plane drive `Stitching` `PLANAR_PROJECTION`.
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
- `Requires:` two or more stereo-capable devices; the calibration origin device must have an IMU and see the floor; `depthai-nodes[box-measurement]` (open3d) on the host
- `Input:` stereo depth and IMU of the origin device for the plane fit, then live undistorted `CAM_B` at native sensor size per device
- `Output:` the fitted plane in the terminal, `Input - <device id>` topics and a `Birds-eye view` topic
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
- `find_origin` reads the origin device and socket from the calibration. `estimate_ground_plane` runs `StereoDepth` (no decimation), a host organized `PointCloud` in the origin socket frame and the `IMU` on that device into `AutoSupportPlane` from depthai-nodes.
- The second pipeline reads the native `CAM_B` size from `getConnectedCameraFeatures`, requests an undistorted output of exactly that size per device and feeds it into a host `Stitching` node in `PLANAR_PROJECTION` mode configured with `setPlane` and `setMaxRange`.

## Constraints

- At least two devices are required; moving a device invalidates `calibration.json` until `--calibrate` is run.
- The metric scale comes from a `CAM_B`/`CAM_C` stereo pair or from `--known-distance`.
- The devices are not hardware-synchronized; frames are grouped within one frame period.
- The projection inputs must be undistorted and at the sensor's native size: on depthai 3.12 a resized output makes the node report that no input sees the plane, and distorted frames paint false content beside the cameras. That is why the example uses `CAM_B` and the view is grayscale.
- The multi-device pipeline and calibration APIs require `depthai>=3.12`.

## Related Examples

- [tutorials/multiple-devices/multi-device-calibration](https://github.com/luxonis/oak-examples/tree/main/tutorials/multiple-devices/multi-device-calibration): use this when you only need the calibration file
- [tutorials/multiple-devices/multi-device-point-cloud](https://github.com/luxonis/oak-examples/tree/main/tutorials/multiple-devices/multi-device-point-cloud): merged 3D point cloud of all devices
- [tutorials/multiple-devices/spatial-detection-fusion](https://github.com/luxonis/oak-examples/tree/main/tutorials/multiple-devices/spatial-detection-fusion): fused 3D detections from calibrated devices

## Validation

- `Run:` `python3 main.py --devices <id-or-ip> <id-or-ip>`
- `Success looks like:` the terminal reports a plausible camera height above the ground and the Visualizer shows a top-down floor view in which floor patterns keep their shape
- `Common failure meaning:` no ground plane was found (the origin device does not see the floor), the origin device has no IMU, the calibration is stale, or objects above the floor look smeared, which is expected
