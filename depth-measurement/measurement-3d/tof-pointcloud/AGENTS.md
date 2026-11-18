# AGENTS.md

## Summary

This is the ToF point-cloud reference in the repo. Use it when you need ToF depth aligned to a color camera, a colorized point cloud in the DepthAI Visualizer, and runtime switching between close, mid, and far ToF range profiles.

## Use This Example When

- You need ToF depth aligned to a color camera.
- You want a colorized point cloud in the browser-based Visualizer.
- You need to change the ToF range profile at runtime without restarting the pipeline.

## Do Not Use This Example When

- You need a ToF-only device without a color camera.
- You need individual ToF filter controls; this example only switches presets.
- You need stereo depth instead of ToF. Use [rgbd-pointcloud](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/measurement-3d/rgbd-pointcloud).

## Quick Facts

- `Category:` `depth-measurement/measurement-3d/tof-pointcloud`
- `Shape:` `script+standalone`
- `Primary task:` RGB-aligned ToF point-cloud visualization with runtime range switching
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Runs on:` host Python with RVC2 or RVC4, or standalone on RVC4
- `Requires:` a device with a ToF sensor and a color camera
- `Output:` Visualizer topics `Point Cloud` (`3d`), `Color` and `ToF Mode` (`images`)

## Read First

- [main.py](main.py): pipeline and key handling loop
- [utils/tof_mode_control.py](utils/tof_mode_control.py): range modes, key handling, and mode overlay
- [utils/arguments.py](utils/arguments.py): CLI arguments
- [oakapp.toml](oakapp.toml): standalone packaging

## Architecture

- Based on `depthai-core/examples/python/ToF/tof_pointcloud.py`.
- `ToF` uses automatic socket selection and starts with the far-range preset.
- Color uses `CAM_A` on RVC4 or `CAM_C` on RVC2. An undistorted 640x400 `RGB888i` output feeds alignment and point-cloud color. A second NV12 output is MJPEG-encoded for the `Color` stream.
- Host `ImageAlign` aligns ToF depth to color. `PointCloud` combines aligned depth and color in millimeters, in the color camera coordinate system.
- `ToFModeControl` is a `HostNode` that follows the manual-camera-control pattern. The main loop passes `RemoteConnection.waitKey()` keys to it. Keys `1`, `2`, and `3` send a `ToFConfig` range profile to `tofBaseInputConfig` without restarting the pipeline. On RVC2 it also sends the matching `ImageFiltersConfig` preset; RVC4 filters on the device.
- `ToFModeControl` publishes an `ImgAnnotations` overlay with the active mode, timestamped from the color frames.

## Constraints

- Requires a color camera at the selected socket as well as ToF.
- Excluded from CI runnability tests because the test devices have no ToF sensor (see [tests/constants.py](https://github.com/luxonis/oak-examples/blob/main/tests/constants.py)).
- Peripheral mode sends color and depth frames to the host for alignment, so a slow network link lowers FPS. Standalone mode avoids this.

## Related Examples

- [rgbd-pointcloud](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/measurement-3d/rgbd-pointcloud): stereo-depth point cloud alternative
- [manual-camera-control](https://github.com/luxonis/oak-examples/tree/main/camera-controls/manual-camera-control): source of the key-press control and overlay pattern

## Validation

- Run `python3 main.py --device <device-ip>` or `oakctl app run .` on an RVC4 ToF device.
- Open the Visualizer and display the `Point Cloud` topic in 3D.
- Success: a live colorized point cloud; pressing `1`, `2`, `3` changes the highlighted mode in the `ToF Mode` overlay and the depth range without stopping the stream.
