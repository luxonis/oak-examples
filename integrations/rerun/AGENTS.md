# AGENTS.md

## Summary

This is the repository reference for streaming DepthAI data into Rerun Viewer. Use it when you want external logging/visualization of frames and point clouds without building a custom UI or relying on the DepthAI Visualizer.

## Use This Example When

- You need Rerun as the primary viewer.
- You want a host node that logs image and point-cloud data directly into Rerun.
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
- `Primary task:` log color, mono, and optional point-cloud data into Rerun
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none in-repo; external Rerun Viewer
- `Runs on:` RVC2 peripheral, RVC4 peripheral, and RVC4 standalone packaging; point-cloud mode requires stereo cameras
- `Requires:` Rerun dependency/runtime, color camera on `CAM_A`, and stereo mono pair for point-cloud mode
- `Input:` RGB stream from `CAM_A`, optional mono streams from `CAM_B/C`, optional stereo-derived point cloud
- `Output:` Rerun entities `Color`, `Left`, `Right`, and `Pointcloud`
- `Models:` none
- `Visualizer / UI:` local Rerun Viewer or served Rerun web viewer

## Read First

- [README.md](README.md): viewer modes and CLI flags
- [main.py](main.py): pipeline branching, Rerun startup, and serve/spawn behavior
- [utils/host_rerun.py](utils/host_rerun.py): the threaded host node that logs images and point clouds
- [utils/arguments.py](utils/arguments.py): CLI surface, especially `--serve`
- [oakapp.toml](oakapp.toml): standalone entrypoint defaults

## Architecture

- `main.py` always creates an RGB stream from `CAM_A`.
- Optional mono streams from `CAM_B/C` are added when `--left`, `--right`, or `--pointcloud` requires them.
- Point-cloud mode builds:
  - `StereoDepth`
  - `ImageAlign` aligned to RGB
  - `PointCloud`
- The custom [utils/host_rerun.py](utils/host_rerun.py) threaded host node consumes the selected streams and logs them into Rerun.
- Viewer startup is controlled before the pipeline runs:
  - `rr.spawn(...)` for local viewer mode
  - `rr.serve(...)` when `--serve <PORT>` is provided

## Data Flow

- `CAM_A -> Rerun host node -> rr.Image("Color")`
- `optional CAM_B/C -> Rerun host node -> rr.Image("Left"/"Right")`
- `CAM_B/C -> StereoDepth -> ImageAlign -> PointCloud -> Rerun host node -> rr.Points3D("Pointcloud")`

## Modification Guide

- `Safe to change:` viewer mode defaults, topic/entity names, resolution, FPS defaults
- `Requires care:` Rerun startup mode, point-cloud/color alignment assumptions, and host-node queue sizing
- `Likely to break if changed blindly:` point-cloud color mapping in [utils/host_rerun.py](utils/host_rerun.py), or the standalone entrypoint defaults in [oakapp.toml](oakapp.toml)

## Common Adaptations

- `To default to web serving:` start from the `--serve` branch in [main.py](main.py)
- `To remove point-cloud support:` keep the RGB/mono logging path and drop the stereo branch
- `To switch to another external viewer:` compare with [../foxglove](../foxglove/)
- `To keep the RGBD baseline and leave Rerun behind:` compare with [../../depth-measurement/3d-measurement/rgbd-pointcloud](../../depth-measurement/3d-measurement/rgbd-pointcloud/)

## Constraints

- The example always creates the RGB stream from `CAM_A`; there is no no-color mode.
- `Pointcloud` logging uses the latest color frame for coloring and assumes that RGB and point-cloud frame layout stay compatible.
- [utils/host_rerun.py](utils/host_rerun.py) flips the X axis because the returned point cloud is currently reversed.
- [oakapp.toml](oakapp.toml) hardcodes `--serve 9090 -fps 20`, which is more opinionated than the README’s generic examples.

## Non-Obvious Repo Conventions

- This example uses `pipeline.create(Rerun).build(...)` rather than explicit output queues in `main.py`; the logging loop lives inside the host node.
- `--serve <PORT>` serves the web viewer on the chosen port, but the Rerun websocket URL still follows the default behavior described in the README.
- There is no `dai.RemoteConnection` in this example; all viewing happens in Rerun.

## Related Examples

- [../foxglove](../foxglove/): use this when you want another external viewer integration with similar stream types
- [../../depth-measurement/3d-measurement/rgbd-pointcloud](../../depth-measurement/3d-measurement/rgbd-pointcloud/): use this when you need the point-cloud baseline without Rerun
- [../../depth-measurement/wls-filter](../../depth-measurement/wls-filter/): use this when you need host-side stereo post-processing rather than viewer integration
- [../../tutorials/camera-demo](../../tutorials/camera-demo/): use this when you need a smaller camera baseline before adding Rerun

## Validation

- `Run:` `python3 main.py`
- `Serve mode:` `python3 main.py --serve 9090`
- `Standalone run:` `oakctl app run .`
- `Success looks like:` Rerun opens locally or is served remotely, and `Color` plus any enabled `Left`, `Right`, or `Pointcloud` entities update live
- `Common failure meaning:` Rerun runtime dependencies are unavailable, stereo hardware is missing for point-cloud mode, or the hardcoded standalone defaults in [oakapp.toml](oakapp.toml) were not accounted for
