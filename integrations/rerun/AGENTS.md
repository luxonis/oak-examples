# AGENTS.md

## Summary

This is the repository reference for streaming DepthAI data into Rerun Viewer. Use it when you want external logging/visualization of frames and point clouds without building a custom UI or relying on the DepthAI Visualizer.

## Use This Example When

- You need Rerun as the primary viewer.
- You want a host loop that logs video, depth, detections, and IMU data directly into Rerun.
- You need a packaged example that can either spawn a local viewer or serve one over the network.
- You want a simple external-visualization bridge rather than a robotics middleware integration.

## Do Not Use This Example When

- You need the DepthAI Visualizer.
- You need Foxglove specifically.
- You need a custom frontend or service-based app.
- You need a pure on-device pipeline with no host logging stage.

## Quick Facts

- `Category:` `integrations/rerun`
- `Shape:` `script+standalone`
- `Primary task:` log video, depth, detections, IMU, and device health into Rerun
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none in-repo; external Rerun Viewer
- `Runs on:` RVC2 peripheral, RVC4 peripheral, and RVC4 standalone packaging
- `Requires:` Rerun dependency/runtime; a color camera for detections, and a stereo pair or ToF sensor for depth and 3D detections
- `Input:` every color and mono camera, `dai.node.Depth`, `IMU`, and `SystemLogger`
- `Output:` Rerun entities under `oak/`, `imu/`, and `device/` (see Data Flow)
- `Models:` YOLOv6-nano COCO from the model zoo ([depthai_models](depthai_models))
- `Visualizer / UI:` local Rerun Viewer or served Rerun web viewer

## Read First

- [README.md](README.md): viewer modes and CLI flags
- [main.py](main.py): pipeline branching, Rerun startup, and serve/spawn behavior
- [utils/rerun_logging.py](utils/rerun_logging.py): one log function per message type, and the default blueprint
- [utils/rig.py](utils/rig.py): calibrated camera transforms, IMU frame, and housing mesh
- [utils/arguments.py](utils/arguments.py): CLI surface, especially `--serve`
- [oakapp.toml](oakapp.toml): standalone entrypoint defaults

## Architecture

- `main.py` streams every color and mono camera as on-device H.264. ToF and thermal sensors are placed on the rig but not streamed.
- Detections run on `CAM_A` when it is color, otherwise on the first color camera.
- With a stereo pair or ToF sensor, `dai.node.Depth` feeds a `SpatialDetectionNetwork`, whose `passthroughDepth` is the logged depth. Without depth, a `DetectionNetwork` logs 2D boxes only.
- Viewer startup and the calibrated rig are logged before the pipeline runs, with `rr.script_setup(...)` choosing spawn, serve, connect, or save from the CLI.
- One host loop waits on all output queues with `dai.MessageQueue.getAny(...)` and passes each message to its log function.

## Data Flow

- `Camera -> VideoEncoder (H.264) -> rr.VideoStream("oak/<camera>/video")` with a per-frame `rr.Pinhole`
- `Depth -> SpatialDetectionNetwork.passthroughDepth -> rr.DepthImage("oak/<camera>/depth")`
- `SpatialDetectionNetwork.out -> rr.Boxes2D("oak/<camera>/video/detections")` and `rr.Points3D("oak/<camera>/detections")`
- `IMU -> rr.Measurements("imu/accel", "imu/gyro")` and `rr.Arrows3D("oak/<camera>/imu/accel")`
- `SystemLogger -> rr.Measurements("device/temperature/*", "device/cpu/*", "device/memory/*")`

## Modification Guide

- `Safe to change:` viewer mode defaults, topic/entity names, resolution, FPS defaults
- `Requires care:` `COLOR_VIDEO_SIZE` must keep the detection model's aspect ratio; only the video queues may block (a dropped H.264 frame corrupts video until the next keyframe, and other blocking queues stall the device)
- `Likely to break if changed blindly:` the mesh tables in [utils/rig.py](utils/rig.py), or the standalone entrypoint defaults in [oakapp.toml](oakapp.toml)

## Common Adaptations

- `To swap the detection model:` change the YAMLs in [depthai_models](depthai_models)
- `To switch to another external viewer:` compare with [integrations/foxglove](https://github.com/luxonis/oak-examples/tree/main/integrations/foxglove)
- `To keep the RGBD baseline and leave Rerun behind:` compare with [depth-measurement/measurement-3d/rgbd-pointcloud](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/measurement-3d/rgbd-pointcloud)

## Constraints

- Calibration comes from `Device.getCalibration()`, which corrects IMU extrinsics that some BNO08x EEPROMs store as identity; uncalibrated boards fall back to `readCalibration()`.
- Calibrated IMU readings are already rotated into the axes of the camera the IMU extrinsics point to, so the IMU frame carries only a translation.
- `SpatialDetectionNetwork` doesn't accept a `ToF` node as its depth source; going through `dai.node.Depth` avoids that.
- On RVC2 the detection network uses 7 shaves, as in the spatial-detections example (4 on OAK-D Lite). Its input is non-blocking with one slot, so it always runs on the newest frame.
- The housing mesh is found by `Device.getDeviceName()`, anchored to the product's reference camera, downloaded once from `luxonis/depthai-ros`, and cached in `~/.cache/oak-examples/meshes`.
- DepthAI spatial coordinates are already in Rerun's RDF camera convention, in millimetres.

## Non-Obvious Repo Conventions

- There is no `dai.RemoteConnection` in this example; all viewing happens in Rerun.
- The timeline is `device_time`, taken from each message's `getTimestampDevice()`, so all sensors share one clock.
- [oakapp.toml](oakapp.toml) uses a base image with Python 3.12, which `rerun-sdk` needs.

## Related Examples

- [integrations/foxglove](https://github.com/luxonis/oak-examples/tree/main/integrations/foxglove): use this when you want another external viewer integration with similar stream types
- [neural-networks/object-detection/spatial-detections](https://github.com/luxonis/oak-examples/tree/main/neural-networks/object-detection/spatial-detections): use this for the spatial detection pipeline with the DepthAI Visualizer
- [depth-measurement/measurement-3d/rgbd-pointcloud](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/measurement-3d/rgbd-pointcloud): use this when you need the point-cloud baseline without Rerun
- [depth-measurement/wls-filter](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/wls-filter): use this when you need host-side stereo post-processing rather than viewer integration
- [tutorials/camera-demo](https://github.com/luxonis/oak-examples/tree/main/tutorials/camera-demo): use this when you need a smaller camera baseline before adding Rerun

## Validation

- `Run:` `python3 main.py`
- `Serve mode:` `python3 main.py --serve`, then open `http://<IP>:9090/?url=rerun%2Bhttp://<IP>:9876/proxy`
- `Standalone run:` `oakctl app run .`
- `Success looks like:` Rerun opens locally or is served remotely, and the device mesh, camera frustums, video, depth, detections, and IMU and device-health plots update live
- `Common failure meaning:` Rerun runtime dependencies are unavailable (`rerun-sdk` needs Python 3.11 or newer), or the model zoo download failed
