# AGENTS.md

## Summary

This is the repository reference for measuring boxes seen by one or more OAK 4 devices with the depthai-nodes `BoxMeasurer` node, with the support plane found and kept by the `AutoSupportPlane` node. Use it when several views must give one measurement per box.

## Use This Example When

- You need box dimensions from several devices that see different sides of the same box.
- You want to see `BoxMeasurer` fed with one view per device and `AutoSupportPlane` fitted to the merged depth of all devices.
- You want a multi-device pipeline that groups frames by a sync threshold, with optional PTP frame sync on all cameras.

## Do Not Use This Example When

- You need a full single-device box measurement app with a custom frontend or a standalone OAK App; use [apps/box-measurement](https://github.com/luxonis/oak-examples/tree/main/apps/box-measurement). This example also runs with one device, but only as a host script with the Visualizer.
- You have RVC2 devices or devices without a stereo pair, such as OAK 4 S.
- The boxes move, for example on a conveyor, and your devices cannot use PTP; without PTP only static boxes are measured correctly.

## Quick Facts

- `Category:` `tutorials/multiple-devices/multi-device-box-measurement`
- `Shape:` `multi-device-host`
- `Primary task:` measure boxes from one or more views, with automatic support plane calibration
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` none
- `Frontend:` none
- `Runs on:` host mode only, with one or more RVC4 devices in one pipeline
- `Requires:` CAM_A, CAM_B and CAM_C on every device; an IMU on the first device; with two or more devices, a shared textured scene for the multi-device calibration, and for moving boxes (`--ptp`) a PTP-capable Ethernet network and Luxonis OS 1.35.0 or newer; `depthai-nodes[box-measurement]` (open3d) on the host
- `Input:` live undistorted `CAM_A` color and depth aligned to it per device, plus accelerometer data of the first device
- `Output:` support plane messages in the terminal; `Color - <device id>` and `Boxes - <device id>` topics per device
- `Models:` `luxonis/box-instance-segmentation` (inside `BoxMeasurer`, on each device); the `Depth` node picks neural depth on RVC4
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`; `q` quits

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [utils/box_overlay.py](utils/box_overlay.py)
- [utils/calibration.py](utils/calibration.py)
- [utils/arguments.py](utils/arguments.py)

## Architecture

- With two or more devices, [utils/calibration.py](utils/calibration.py) runs `dai.beta.node.MultiDeviceCalibration` on the stereo pairs in its own pipeline on the first run and saves `calibration.json`; later runs load it with `MultiDeviceCalibrationHandler`. With one device there is no calibration, and the shared coordinates are that device's `CAM_A` frame.
- [main.py](main.py) builds one `dai.Pipeline(createImplicitDevice=False)`, applies the calibration with `pipeline.setMultiDeviceCalibration` and creates the per-device nodes with `pipeline.create(node, device)`.
- Per device, `main.py` makes the `CAM_A`, `CAM_B` and `CAM_C` cameras, with `FrameSyncMode.TIME_PTP` when there are two or more devices and `--ptp` is set. The `Depth` node reuses the existing stereo cameras of its device, so their PTP setting applies to depth too. Depth is aligned to the undistorted `640x400` color output; together they are one view.
- Without `--ptp`, `main.py` sets one sync threshold of half a frame period on `BoxMeasurer.build(views, syncThreshold=...)` and on the support plane `PointCloud.sync`. With `--ptp`, both keep the default of 10 ms. This follows depthai-core's `multi_device_frame_sync.py`: host sync by default, PTP opt-in.
- `BoxMeasurer.build(views, ...)` runs the box model and tracker on each device and associates, tracks and measures the boxes on the host. Its output gives each box's detections by view index, which `BoxOverlay` draws on that view's color stream.
- A separate host `PointCloud` merges the depth of all devices in millimeters. `AutoSupportPlane` in `CONTINUOUS` mode fits the support plane to it, with gravity from the first device's IMU rotated into the shared coordinates.
- The main loop passes each new plane to `measurer.setSupportPlane`. It skips the repeated plane that every passed check sends, because setting a plane resets the aggregated dimensions.

## Data Flow

- `per device: CAM_A RGB888i 640x400 -> BoxMeasurer view color, Color - <device id>`
- `per device: CAM_B + CAM_C -> Depth (aligned to CAM_A) -> BoxMeasurer view depth, PointCloud.getDepthInput(device id)`
- `PointCloud (mm, shared coordinates) + first device IMU ACCELEROMETER_RAW -> AutoSupportPlane -> main loop -> BoxMeasurer.setSupportPlane`
- `BoxMeasurer -> BoxMeasurements -> BoxOverlay (one per view) -> Boxes - <device id>`

## Modification Guide

- `Safe to change:` `SIZE` (keep the 16:10 aspect ratio of the box model input), `--fps_limit`, the `AutoSupportPlaneConfig` fields and the overlay label
- `Requires care:` the PTP setting and the sync threshold, since `BoxMeasurer` groups views by host timestamp and drops frames whose views are not within the threshold, and a threshold larger than half a frame period can group frames captured one frame apart; creating the stereo cameras before the `Depth` node, otherwise it makes its own cameras without PTP
- `Likely to break if changed blindly:` calling `setSupportPlane` on every `AutoSupportPlane` result; a support plane cloud in other units or coordinates than `BoxMeasurer` uses

## Common Adaptations

- `To measure against a fixed plane:` use `AutoSupportPlaneConfig.Mode.ON_START`, or save `result.plane` with `toJsonFile` and pass it to `BoxMeasurer.build(views, supportPlane=...)`.
- `To change the detection threshold:` pass `confidenceThreshold` to `BoxMeasurer.build`, or call `measurer.setConfidenceThreshold` while running.
- `To use the measurements:` read `measurer.out` (`BoxMeasurements`) with an output queue; each `BoxMeasurementResult` has `box_id`, `measurement_status` and `dimensions`.

## Constraints

- RVC4 only: `BoxMeasurer` raises `ValueError` for other platforms.
- With two or more devices, moving boxes need PTP-synchronized frames (`--ptp`). Without it, the views of one frame are captured up to half a frame period apart, so only static boxes are measured correctly. Moving a device invalidates `calibration.json` until `--calibrate` is run.
- Boxes stay `ineligible` until the support plane is found. The node takes the plane perpendicular to gravity with the most points, so the support plane must be the largest such surface in the merged depth.
- Boxes cut by the frame border of a view are not detected in that view.
- The multi-device pipeline and the multi-stream `PointCloud` require `depthai>=3.12`.

## Non-Obvious Repo Conventions

- Excluded from the runnability tests in `tests/constants.py`: it needs RVC4 devices, and discovery skips IP-only devices without `--include-ip`.
- **Support plane calibration** here is automatic; it is unrelated to the **multi-device calibration** of the device poses.

## Related Examples

- [apps/box-measurement](https://github.com/luxonis/oak-examples/tree/main/apps/box-measurement): full single-device box measurement app with a custom frontend
- [tutorials/multiple-devices/multi-device-point-cloud](https://github.com/luxonis/oak-examples/tree/main/tutorials/multiple-devices/multi-device-point-cloud): merged 3D point cloud of all devices
- [tutorials/multiple-devices/multi-device-birds-eye-view](https://github.com/luxonis/oak-examples/tree/main/tutorials/multiple-devices/multi-device-birds-eye-view): `AutoSupportPlane` on one device driving a top-down view
- [tutorials/multiple-devices/multi-device-calibration](https://github.com/luxonis/oak-examples/tree/main/tutorials/multiple-devices/multi-device-calibration): use this when you only need the calibration file

## Validation

- `Run:` `python3 main.py --devices <id-or-ip> <id-or-ip>`, or with one device `python3 main.py --devices <id-or-ip>`
- `Success looks like:` the terminal logs `Support plane found ... m from the origin camera.` with a plausible distance, and boxes in the Visualizer change from `ineligible` to `measured` with dimensions near a tape measurement; a box seen by two devices has one ID on both
- `Common failure meaning:` no `Boxes` output with two or more devices and `--ptp` (PTP is not working; check PTP or run without `--ptp`), split or too large moving boxes without `--ptp` (expected without PTP), boxes stay `ineligible` (no support plane found: the devices see too little of the support plane), doubled boxes (stale multi-device calibration), or `ValueError` from `BoxMeasurer` (not an RVC4 device)
