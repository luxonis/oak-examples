# AGENTS.md

## Summary

This is the runtime stereo dynamic-calibration workflow reference in the repo. Use it when you need an interactive calibration HUD, coverage/quality feedback, and host-driven control over applying or flashing calibration states.

## Use This Example When

- You need a reference for `dai.node.DynamicCalibration`.
- You want a rich overlay-driven workflow for loading images, recalibrating, and checking quality.
- You need to inspect or flash calibration states from the host.
- You want the strongest repo example for calibration UX rather than raw stereo depth output.

## Do Not Use This Example When

- You need a minimal stereo-depth baseline.
- You need RGBD point clouds or neural inference.
- You need ToF.
- You do not want any example that can flash EEPROM from the keyboard.

## Quick Facts

- `Category:` `depth-measurement/dynamic-calibration`
- `Shape:` `script+standalone`
- `Primary task:` interactive runtime stereo calibration and calibration management
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` stereo-capable devices with `CAM_B` and `CAM_C`
- `Requires:` stereo mono pair, stored calibration, and a user who understands the calibration lifecycle
- `Input:` full-resolution stereo frames plus runtime key commands
- `Output:` `Left`, `Right`, `Depth`, and `DynCalib HUD`
- `Models:` none
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md): keyboard control guide and operator workflow
- [main.py](main.py): pipeline setup, queue wiring, and device binding
- [utils/dynamic_controler.py](utils/dynamic_controler.py): the real heart of the example, including HUD, modal overlays, calibration queue handling, and flash operations
- [utils/dynamic_calibration_interactive.py](utils/dynamic_calibration_interactive.py): related calibration interaction support
- [utils/arguments.py](utils/arguments.py): CLI surface
- [oakapp.toml](oakapp.toml): packaging path and extra runtime dependencies

## Architecture

- `CAM_B` and `CAM_C` provide full-resolution NV12 frames.
- The same stereo streams feed both:
  - `StereoDepth` for the live depth view
  - `DynamicCalibration` for calibration operations
- `ApplyDepthColormap` generates the display stream used for the HUD timestamping.
- The custom [utils/dynamic_controler.py](utils/dynamic_controler.py) host node:
  - consumes preview and raw depth
  - drains calibration, coverage, and quality queues after `pipeline.start()`
  - builds help, coverage, quality, status, and depth-HUD overlays
  - handles key commands for calibration apply/revert and EEPROM flashing

## Data Flow

- `CAM_B/C -> StereoDepth -> Depth`
- `CAM_B/C -> DynamicCalibration -> calibration/coverage/quality queues`
- `Depth preview + stereo.depth -> DynamicCalibrationControler -> DynCalib HUD`
- `keyboard input -> DynamicCalibrationControler -> DynamicCalibration inputControl`

## Modification Guide

- `Safe to change:` overlay text, topic names, FPS default, help-panel wording
- `Requires care:` queue wiring after `pipeline.start()`, current/new/old calibration state handling, and any flash-to-EEPROM path
- `Likely to break if changed blindly:` the controller state machine in [utils/dynamic_controler.py](utils/dynamic_controler.py), especially around auto-apply, modal timing, and device flash operations

## Common Adaptations

- `To reuse only the calibration HUD:` keep [utils/dynamic_controler.py](utils/dynamic_controler.py) and feed it your own preview/depth streams and control queues
- `To disable automatic application of new calibration:` change `auto_apply_new` in [utils/dynamic_controler.py](utils/dynamic_controler.py)
- `To build a safer demo:` remove or guard the `p`, `k`, and `f` flash paths before handing it to less experienced operators
- `To compare against simpler stereo tools:` use [../stereo-runtime-configuration](../stereo-runtime-configuration/) or [../stereo-on-host](../stereo-on-host/)

## Constraints

- This example can flash calibration data to EEPROM from the keyboard with `p`, `k`, and `f`; treat it as a high-impact workflow.
- It assumes stereo cameras on `CAM_B` and `CAM_C`.
- The overlay and control flow are host-side; this is not a minimal embedded-only calibration demo.
- The current controller defaults `auto_apply_new = True`, so the README key list is slightly misleading: new calibration may already be applied automatically before the operator presses `n`.

## Non-Obvious Repo Conventions

- The main interaction logic lives in the misspelled [utils/dynamic_controler.py](utils/dynamic_controler.py); that filename is intentional in the current repo state.
- Queue objects for calibration, coverage, quality, and input control are created off device nodes and then injected into the host controller after `pipeline.start()`.
- `DynCalib HUD` is an annotation layer over the depth preview, not a separate image source.
- The controller also supports a movable depth HUD ROI using `w/a/s/d` and `z/x`.

## Related Examples

- [../stereo-runtime-configuration](../stereo-runtime-configuration/): use this when you want runtime stereo parameter tuning rather than calibration workflows
- [../stereo-on-host](../stereo-on-host/): use this when you want host-side stereo benchmarking rather than calibration control
- [../calc-spatial-on-host](../calc-spatial-on-host/): use this when you need host-side ROI spatial measurement
- [../wls-filter](../wls-filter/): use this when the host-side focus is disparity filtering instead of calibration state management

## Validation

- `Run:` `python3 main.py`
- `Standalone run:` `oakctl app run .`
- `Success looks like:` the Visualizer shows `Left`, `Right`, `Depth`, and `DynCalib HUD`, and the keyboard commands trigger help, coverage, quality, and calibration-state feedback
- `Common failure meaning:` the device lacks the required stereo topology, calibration access is failing, or the operator is triggering flash/apply paths without valid calibration state
