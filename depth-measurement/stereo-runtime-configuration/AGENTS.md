# AGENTS.md

## Summary

This is the simplest runtime stereo-parameter tuning example in the repo. Use it when you need to change `StereoDepth` settings live from the host and visualize the effect immediately in the DepthAI Visualizer.

## Use This Example When

- You need a small reference for `stereo.inputConfig`.
- You want to toggle median filtering, left-right check, and confidence threshold live.
- You need a stereo-depth demo with a host-side configuration overlay but no custom frontend.
- You want a lower-risk alternative to the dynamic-calibration workflow.

## Do Not Use This Example When

- You need host-side disparity computation or quality comparison.
- You need spatial ROI measurement or point clouds.
- You need ToF.
- You need a broader stereo tuning surface than the three parameters exposed here.

## Quick Facts

- `Category:` `depth-measurement/stereo-runtime-configuration`
- `Shape:` `script+standalone`
- `Primary task:` live host-driven reconfiguration of `StereoDepth`
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` devices with `CAM_A`, `CAM_B`, and `CAM_C`
- `Requires:` stereo mono pair plus RGB preview camera
- `Input:` RGB preview from `CAM_A`, stereo pair from `CAM_B/C`, and keyboard commands
- `Output:` `Color`, `Depth`, and `Stereo config`
- `Models:` none
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md): key controls and runtime behavior
- [main.py](main.py): pipeline layout, sync/demux setup, and live config wiring
- [utils/stereo_config_controller.py](utils/stereo_config_controller.py): the host node that owns config state and overlay text
- [utils/arguments.py](utils/arguments.py): CLI surface
- [oakapp.toml](oakapp.toml): packaging path

## Architecture

- `CAM_A` provides a color preview stream.
- `CAM_B` and `CAM_C` feed `StereoDepth`.
- `StereoDepth.setRuntimeModeSwitch(True)` enables live configuration updates.
- The custom [utils/stereo_config_controller.py](utils/stereo_config_controller.py) host node:
  - stores the current stereo config object
  - sends updated config messages to `stereo.inputConfig`
  - emits overlay annotations describing the live settings
- A `Sync` plus `MessageDemux` branch keeps the color preview and depth preview aligned for display.

## Data Flow

- `CAM_A -> preview`
- `CAM_B/C -> StereoDepth -> disparity -> ApplyDepthColormap -> Depth`
- `preview -> StereoConfigController -> Stereo config annotations`
- `keyboard input -> StereoConfigController.out_cfg -> StereoDepth.inputConfig`
- `preview + depth -> Sync -> MessageDemux -> Color + Depth topics`

## Modification Guide

- `Safe to change:` default confidence threshold, default median filter, overlay text, topic names
- `Requires care:` runtime config compatibility, sync/demux topic wiring, and camera resolution/FPS consistency
- `Likely to break if changed blindly:` adding unsupported runtime parameters or removing `setRuntimeModeSwitch(True)`

## Common Adaptations

- `To expose more stereo settings:` extend [utils/stereo_config_controller.py](utils/stereo_config_controller.py) with more key bindings and config mutations
- `To remove the RGB preview:` keep the stereo branch and replace the current sync/display pattern
- `To compare the impact of host-side stereo instead:` switch to [depth-measurement/stereo-on-host](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/stereo-on-host)
- `To move into a calibration-oriented workflow:` switch to [depth-measurement/dynamic-calibration](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/dynamic-calibration)

## Constraints

- The current controller only exposes confidence threshold, median filter, and left-right check.
- The example assumes `CAM_A` for preview and `CAM_B/C` for stereo.
- The stereo overlay is annotation-only; there is no persisted configuration UI beyond key presses.

## Non-Obvious Repo Conventions

- `Stereo config` is an annotation layer placed on the color stream.
- The controller mutates and resends one `StereoDepthConfig` instance rather than rebuilding configuration from scratch each time.
- The depth view is based on colorized disparity, not raw depth.

## Related Examples

- [depth-measurement/stereo-on-host](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/stereo-on-host): use this when you need host-side stereo computation and comparison
- [depth-measurement/dynamic-calibration](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/dynamic-calibration): use this when you need richer stereo control around calibration state
- [depth-measurement/calc-spatial-on-host](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/calc-spatial-on-host): use this when the host-side work should be ROI spatial measurement
- [depth-measurement/measurement-3d/rgbd-pointcloud](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/measurement-3d/rgbd-pointcloud): use this when the goal is RGBD fusion and point-cloud output

## Validation

- `Run:` `python3 main.py`
- `Standalone run:` `oakctl app run .`
- `Success looks like:` the Visualizer shows `Color`, `Depth`, and `Stereo config`, and pressing `k`, `l`, `,`, or `.` updates the overlay and depth behavior
- `Common failure meaning:` the device lacks the expected camera topology, the stereo config path is not in runtime-switch mode, or the overlay/controller wiring is broken
