# AGENTS.md

## Summary

This is the minimal RGBD point-cloud reference in the repo. Use it when you need the smallest example that aligns unified depth to a color stream and publishes a point cloud without adding custom host processing or neural inference.

## Use This Example When

- You need a clean baseline for `Depth + RGBD + pcl`.
- You want to align depth to RGB or optionally colorize the point cloud from the right mono camera.
- You need a point-cloud reference that still works with the Visualizer rather than Open3D.
- You want a simple starting point before moving to measurement or frontend-heavy examples.

## Do Not Use This Example When

- You need box fitting, spatial ROI measurement, or host-side post-processing.
- You need ToF-specific depth.
- You need a browser frontend or a desktop GUI.
- You need neural inference fused into the point-cloud pipeline.

## Quick Facts

- `Category:` `depth-measurement/3d-measurement/rgbd-pointcloud`
- `Shape:` `script+standalone`
- `Primary task:` align unified depth to a color source and publish a point cloud
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` stereo-capable devices with `CAM_B/C` and either `CAM_A` or the right mono camera
- `Requires:` stereo mono pair, calibration, and optionally RGB camera if `--mono` is not used
- `Input:` unified depth from `dai.node.Depth`; color from `CAM_A` by default or right mono with `--mono`
- `Output:` `preview` and `pointcloud`
- `Models:` none
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md): usage notes and mode selection
- [main.py](main.py): complete pipeline and alignment branch
- [utils/arguments.py](utils/arguments.py): CLI surface, especially `--mono`
- [oakapp.toml](oakapp.toml): packaging path

## Architecture

- `Depth` owns depth-source selection and stereo camera setup when stereo is selected.
- `RGBD` is used to fuse depth with a selected color source.
- The color source is either:
  - `CAM_A` in RGB mode
  - the right mono camera when `--mono` is set
- RVC4 uses `ImageAlign` to align depth to the chosen color stream.
- RVC2 uses `stereo.inputAlignTo` instead of a separate `ImageAlign` node.
- The Visualizer receives both the color preview and the generated point cloud.

## Data Flow

- `Depth -> aligned depth`
- `CAM_A or right mono -> RGBD.inColor`
- `aligned depth + color -> RGBD -> pointcloud`
- `selected color stream -> preview`

## Modification Guide

- `Safe to change:` topic names, preview sizing, default color source choice, projector usage
- `Requires care:` alignment path differences between RVC2 and RVC4, camera socket assumptions, output frame types
- `Likely to break if changed blindly:` switching image size without keeping color/depth alignment consistent, or assuming every device supports an IR projector

## Common Adaptations

- `To colorize from mono by default:` start from the `--mono` branch in [main.py](main.py)
- `To reuse this as a point-cloud baseline for another task:` keep the `Depth` and `RGBD` branch and replace the Visualizer topics
- `To add host-side geometry processing:` compare against [depth-measurement/3d-measurement/box-measurement](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/3d-measurement/box-measurement) after this baseline is working
- `To move to ToF:` use [depth-measurement/3d-measurement/tof-pointcloud](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/3d-measurement/tof-pointcloud) instead

## Constraints

- This example assumes a stereo mono pair on `CAM_B` and `CAM_C`.
- RGB mode assumes the color camera is on `CAM_A`.
- `device.setIrLaserDotProjectorIntensity(1)` may fail on devices that do not expose that feature.
- The point cloud is published directly from `RGBD`; there is no host-side filtering or resampling layer here.

## Non-Obvious Repo Conventions

- `preview` is the selected color stream, not a rendered depth image.
- The `--mono` flag does not disable RGBD; it changes the colorization source to the right mono camera.
- [oakapp.toml](oakapp.toml) provides packaging, but this is still a valid peripheral-mode reference.

## Related Examples

- [depth-measurement/3d-measurement/box-measurement](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/3d-measurement/box-measurement): use this when you need segmentation-driven measurements on top of RGBD point clouds
- [depth-measurement/3d-measurement/tof-pointcloud](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/3d-measurement/tof-pointcloud): use this when the point cloud should come from a ToF sensor
- [depth-measurement/stereo-on-host](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/stereo-on-host): use this when you need host-side stereo comparison rather than a point cloud
- [tutorials/camera-stereo-depth](https://github.com/luxonis/oak-examples/tree/main/tutorials/camera-stereo-depth): use this when you need a simpler depth baseline before RGBD fusion

## Validation

- `Run:` `python3 main.py`
- `Standalone run:` `oakctl app run .`
- `Success looks like:` the Visualizer shows `preview` plus `pointcloud`, and the point cloud follows the selected color source
- `Common failure meaning:` the device lacks the required camera topology, calibration is missing, or RGB/depth alignment assumptions do not match the hardware
