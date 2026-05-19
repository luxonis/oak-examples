# AGENTS.md

## Summary

This is the repository reference for streaming DepthAI data into Foxglove Studio over a Foxglove WebSocket server. Use it when you need external viewer integration for frames or point clouds rather than the built-in DepthAI Visualizer.

## Use This Example When

- You need Foxglove Studio as the primary viewer.
- You want to stream RGB, left, right, or point-cloud data through a websocket server.
- You need a small integration example with no custom frontend code in the repo.
- You want an external telemetry/visualization sink rather than annotation overlays in the Visualizer.

## Do Not Use This Example When

- You need the DepthAI Visualizer.
- You need browser UI code or frontend/backend services.
- You need a local point-cloud viewer rather than websocket export.
- You need a richer robotics stack than this one-script Foxglove bridge.

## Quick Facts

- `Category:` `integrations/foxglove`
- `Shape:` `script+standalone`
- `Primary task:` stream selected DepthAI topics to Foxglove Studio over websocket
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none in-repo; external Foxglove Studio client
- `Runs on:` RVC2 peripheral, RVC4 peripheral, and RVC4 standalone packaging; point-cloud mode needs a stereo pair
- `Requires:` Foxglove Studio, websocket access to port `8765`, and Open3D for point-cloud preprocessing
- `Input:` optional color from `CAM_A`, optional mono streams from `CAM_B/C`, optional stereo-derived point cloud
- `Output:` Foxglove websocket channels `colorImage`, `leftImage`, `rightImage`, and `pointCloud`
- `Models:` none
- `Visualizer / UI:` Foxglove Studio via Foxglove WebSocket

## Read First

- [README.md](README.md): supported flags and Foxglove connection instructions
- [main.py](main.py): async server startup, pipeline branching, and queue wiring
- [utils/foxglove_utils.py](utils/foxglove_utils.py): schema/channel creation, JPEG serialization, and point-cloud packing
- [utils/arguments.py](utils/arguments.py): CLI surface for stream selection
- [oakapp.toml](oakapp.toml): standalone packaging and dependency install path

## Architecture

- `main.py` runs as an `asyncio` application through `run_cancellable`.
- Stream creation is flag-driven:
  - color from `CAM_A` unless `--no-color`
  - left from `CAM_B` when `--left` or `--pointcloud`
  - right from `CAM_C` when `--right` or `--pointcloud`
- Point-cloud mode builds `StereoDepth` and then:
  - aligns depth to RGB with `ImageAlign` when color is enabled
  - uses raw stereo depth when color is disabled
- `FoxgloveServer` listens on `0.0.0.0:8765`.
- [utils/foxglove_utils.py](utils/foxglove_utils.py) declares ROS-style JSON schemas and serializes frames/point clouds into base64 payloads.

## Data Flow

- `selected camera streams -> output queues -> send_frame() -> Foxglove compressed-image channels`
- `CAM_B/C -> StereoDepth -> optional ImageAlign -> PointCloud -> process_pointcloud() -> pointCloud channel`

## Modification Guide

- `Safe to change:` default stream selection, channel/topic labels, resolution, JPEG quality path, point-cloud downsampling toggle
- `Requires care:` websocket schema compatibility, point-cloud coordinate conventions, and alignment differences between color and no-color modes
- `Likely to break if changed blindly:` the expected Foxglove message schema in [utils/foxglove_utils.py](utils/foxglove_utils.py), or running with no enabled streams after `--no-color`

## Common Adaptations

- `To expose more channels:` extend `create_channels()` and the main event loop in [utils/foxglove_utils.py](utils/foxglove_utils.py) and [main.py](main.py)
- `To disable downsampling:` change `downsample_pcl` in [main.py](main.py) or `process_pointcloud()` in [utils/foxglove_utils.py](utils/foxglove_utils.py)
- `To move to another external viewer:` compare this example with [integrations/rerun](https://github.com/luxonis/oak-examples/tree/main/integrations/rerun)
- `To keep point-cloud logic but use the Visualizer instead:` start instead from [depth-measurement/3d-measurement/rgbd-pointcloud](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/3d-measurement/rgbd-pointcloud)

## Constraints

- This example does not use `dai.RemoteConnection`; there is no built-in Visualizer fallback.
- Point-cloud preprocessing depends on Open3D even though the final viewer is Foxglove.
- If `--no-color` is used without any of `--left`, `--right`, or `--pointcloud`, the example produces no useful streams.
- The standalone `oakapp.toml` entrypoint passes no flags, so packaged runs default to color-only unless the file is edited.

## Non-Obvious Repo Conventions

- The Foxglove server port is fixed at `8765` in [main.py](main.py); it is not currently configurable through CLI arguments.
- `process_pointcloud()` converts millimeters to meters and flips the X axis before publishing.
- Frame channels are serialized as JPEG `CompressedImage` payloads encoded in base64 JSON, not as raw image buffers.
- [oakapp.toml](oakapp.toml) installs `libgl1` and increases pip timeout because the dependency set includes Open3D.

## Related Examples

- [integrations/rerun](https://github.com/luxonis/oak-examples/tree/main/integrations/rerun): use this when you want another external viewer integration with point clouds and frames
- [depth-measurement/3d-measurement/rgbd-pointcloud](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/3d-measurement/rgbd-pointcloud): use this when you need the RGBD/point-cloud baseline without Foxglove
- [depth-measurement/stereo-on-host](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/stereo-on-host): use this when the host-side goal is stereo benchmarking rather than websocket export
- [tutorials/camera-demo](https://github.com/luxonis/oak-examples/tree/main/tutorials/camera-demo): use this when you only need a simple camera baseline before adding external viewer integration

## Validation

- `Run:` `python3 main.py`
- `Standalone run:` `oakctl app run .`
- `Success looks like:` Foxglove Studio connects to `ws://<host>:8765`, the selected channels appear, and frames or point clouds update live
- `Common failure meaning:` no channels were enabled, Foxglove cannot reach port `8765`, stereo hardware is missing for point-cloud mode, or the environment lacks the required Open3D/runtime dependencies
