# AGENTS.md

## Summary

This is the ToF-specific depth and point-cloud tuning demo in the repo. Use it when you need interactive runtime control over ToF filters, side-by-side raw versus filtered point clouds, and a desktop GUI rather than a Visualizer-based stereo example.

## Use This Example When

- You need a ToF reference rather than a stereo-depth reference.
- You want to tune ToF image filters and base configuration live from a GUI.
- You need raw and filtered depth windows plus raw and filtered point-cloud comparison.
- You want a host-side Open3D desktop workflow.

## Do Not Use This Example When

- You need standalone OAK app packaging.
- You need a Visualizer-based pipeline.
- You need RGB alignment or stereo disparity.
- You need a small modular example; this script is intentionally monolithic.

## Quick Facts

- `Category:` `depth-measurement/measurement-3d/tof-pointcloud`
- `Shape:` `script+desktop-ui`
- `Primary task:` interactive ToF filter tuning with raw versus filtered point-cloud visualization
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` none
- `Frontend:` local desktop UI via Tkinter, OpenCV, and Open3D
- `Runs on:` ToF camera devices only; effectively a host-driven RVC2 workflow
- `Requires:` ToF hardware, Python desktop environment, OpenGL-capable Open3D setup, and Tkinter/OpenCV support
- `Input:` raw and filtered ToF depth streams from a `dai.node.ToF` pipeline
- `Output:` `ToF Raw Depth`, `ToF Filtered Depth`, and two Open3D point-cloud windows
- `Models:` none
- `Visualizer / UI:` Tkinter control panel, OpenCV image windows, Open3D visualizers

## Read First

- [README.md](README.md): hardware and host dependency expectations
- [main.py](main.py): entire application, including GUI, Open3D thread, and ToF pipeline
- [requirements.txt](requirements.txt): host dependencies needed for this example

## Architecture

- The entire example lives in [main.py](main.py).
- `camera_pipeline()` builds one `dai.node.ToF` pipeline on `CAM_A`.
- The Tkinter `FilterGUI` owns the runtime controls for:
  - ToF base configuration
  - ToF confidence filter
  - image filters such as speckle, temporal, spatial, and median
  - point-cloud decimation and max-distance controls
- A background Open3D thread maintains two independent point-cloud windows:
  - `RAW Point Cloud`
  - `FINAL Point Cloud`
- The main thread runs the GUI; the camera pipeline runs in a daemon thread.

## Data Flow

- `ToF.rawDepth -> ToF Raw Depth window -> RAW point-cloud generator`
- `ToF.depth -> ToF Filtered Depth window -> FINAL point-cloud generator`
- `Tkinter controls -> config queues -> ToF node runtime configuration`
- `stored latest depth frames -> Open3D point-cloud windows`

## Modification Guide

- `Safe to change:` initial filter defaults, point-cloud decimation defaults, max-distance defaults, window titles
- `Requires care:` the multi-threaded global state for point-cloud updates, camera intrinsics handling, and GUI-to-queue wiring
- `Likely to break if changed blindly:` the Open3D update thread, Tkinter main-thread ownership, and the assumptions that both raw and filtered depth frames are always available

## Common Adaptations

- `To reuse only the ToF pipeline:` extract `camera_pipeline()` and drop the GUI/Open3D sections
- `To change default filter behavior:` edit [main.py](main.py) in `get_initial_filter_params()` and the Tkinter variable defaults
- `To disable point clouds and keep only 2D visualization:` remove the Open3D thread setup and keep the OpenCV windows
- `To compare against stereo point clouds:` use [depth-measurement/measurement-3d/rgbd-pointcloud](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/3d-measurement/rgbd-pointcloud) as the stereo baseline

## Constraints

- The README explicitly notes that standalone mode is not supported here.
- The example depends on a desktop environment; it is a poor fit for headless or container-only execution.
- Open3D initialization can fail on unsupported OpenGL/X11 setups; the script prints Linux/WSL guidance when that happens.
- This is a single large script, so it is less reusable as a code skeleton than the smaller stereo examples.
- The ToF node is built on `CAM_A`, which is a hardware assumption in the current script.

## Non-Obvious Repo Conventions

- Pressing `p` pauses point-cloud updates, not the camera pipeline itself.
- Pressing `1` and `2` triggers manual raw or final point-cloud refresh from the latest stored frames.
- Pressing `v` resets the Open3D views; it does not change ToF filter settings.
- The GUI root runs on the main thread, while the pipeline and OpenCV handling run in a daemon thread.

## Related Examples

- [depth-measurement/measurement-3d/rgbd-pointcloud](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/measurement-3d/rgbd-pointcloud): use this when you want a stereo RGBD point-cloud baseline instead of ToF
- [depth-measurement/wls-filter](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/wls-filter): use this when you want host-side stereo post-processing rather than ToF filtering
- [depth-measurement/dynamic-calibration](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/dynamic-calibration): use this when your goal is stereo calibration workflows rather than ToF tuning
- [depth-measurement/stereo-on-host](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/stereo-on-host): use this when you want another host-processing depth reference built around stereo disparity instead of ToF point clouds

## Validation

- `Run:` `python3 main.py`
- `Success looks like:` the Tkinter control panel opens, OpenCV shows raw and filtered depth, and Open3D shows separate raw and final point clouds
- `Common failure meaning:` the device is not a ToF camera, Open3D/Tkinter desktop dependencies are missing, or the environment does not support the required graphics stack
