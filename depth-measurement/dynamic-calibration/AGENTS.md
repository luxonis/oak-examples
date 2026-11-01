# AGENTS.md

## Summary

Runtime stereo calibration with optional on-start or continuous AutoCalibration and an interactive manual diagnostic HUD. Automatic modes apply validated runtime updates without flashing EEPROM; manual mode retains coverage, quality, apply/revert, and explicit flash controls.

## Use This Example When

- You need a reference for `dai.node.DynamicCalibration`.
- You need a small `dai.node.AutoCalibration` path with visible status and runtime-only updates.
- You want a rich overlay-driven workflow for loading images, recalibrating, and checking quality.
- You need to inspect or flash calibration states from the host.
- You want the strongest repo example for calibration UX rather than raw stereo depth output.

## Do Not Use This Example When

- You need a minimal stereo-depth baseline.
- You need RGBD point clouds or neural inference.
- You need ToF.
- You need an automatic path for sensor modes other than matching 1280x800 or 640x400 on `CAM_B/C`.

## Quick Facts

- `Category:` `depth-measurement/dynamic-calibration`
- `Shape:` `script+standalone`
- `Primary task:` interactive runtime stereo calibration and calibration management
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` stereo-capable devices with `CAM_B` and `CAM_C`
- `Requires:` stereo mono pair, stored calibration, and a user who understands the calibration lifecycle
- `Input:` full-resolution stereo frames; manual key commands or automatic calibration cycles
- `Output:` `Left`, `Right`, `Depth`, `DynCalib HUD`, and automatic-mode console JSON results
- `Models:` none
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md): keyboard control guide and operator workflow
- [main.py](main.py): pipeline setup, queue wiring, and device binding
- [utils/dynamic_controler.py](utils/dynamic_controler.py): the real heart of the example, including HUD, modal overlays, calibration queue handling, and flash operations
- [utils/dynamic_calibration_interactive.py](utils/dynamic_calibration_interactive.py): related calibration interaction support
- [utils/arguments.py](utils/arguments.py): CLI surface
- [utils/auto_calibration.py](utils/auto_calibration.py): automatic node configuration and native sensor-mode checks
- [oakapp.toml](oakapp.toml): packaging path and extra runtime dependencies

## Architecture

- `CAM_B` and `CAM_C` provide full-resolution NV12 frames.
- `--mode manual` remains the default; `--mode on-start` and `--mode continuous` select the optional automatic path. The pipeline's implicit AutoCalibration mode is explicitly `OFF` in all cases.
- The same stereo streams feed both:
  - `StereoDepth` for the live depth view
  - `DynamicCalibration` for calibration operations
- `ApplyDepthColormap` generates the display stream used for the HUD timestamping.
- The custom [utils/dynamic_controler.py](utils/dynamic_controler.py) host node:
  - consumes preview and raw depth
  - drains calibration, coverage, and quality queues after `pipeline.start()`
  - builds help, coverage, quality, status, and depth-HUD overlays
  - handles key commands for calibration apply/revert and EEPROM flashing
- Automatic mode replaces the manual node with `AutoCalibration.build(cam_left, cam_right)`, feeding its internal worker from the cameras' unrectified ISP outputs. It explicitly sets `flashCalibration=False` and retains native confidence/validation defaults. Never copy upstream demo calibration perturbations.
- The same HUD consumes automatic results, displays waiting/pass/fail and confidence scores, and disables manual calibration/flash commands. Accepted results are already applied by the SDK; do not apply rejected results or reapply them from the HUD. A passed result can validate the existing calibration unchanged.

## Data Flow

- `CAM_B/C -> StereoDepth -> Depth`
- `CAM_B/C -> DynamicCalibration -> calibration/coverage/quality queues`
- `Depth preview + stereo.depth -> DynamicCalibrationControler -> DynCalib HUD`
- `keyboard input -> DynamicCalibrationControler -> DynamicCalibration inputControl`
- Automatic alternative: `Camera ISP -> AutoCalibration -> result queue/HUD + console JSON`; SDK applies accepted calibration to runtime geometry. DepthAI 3.11's result cannot be serialized directly via RemoteConnection; inspect HUD annotations instead.

## Modification Guide

- `Safe to change:` overlay text, topic names, FPS default, help-panel wording
- `Requires care:` queue wiring after `pipeline.start()`, current/new/old calibration state handling, and any flash-to-EEPROM path
- `Likely to break if changed blindly:` the controller state machine in [utils/dynamic_controler.py](utils/dynamic_controler.py), especially around auto-apply, modal timing, and device flash operations

## Common Adaptations

- `To reuse only the calibration HUD:` keep [utils/dynamic_controler.py](utils/dynamic_controler.py) and feed it your own preview/depth streams and control queues
- `To disable automatic application of new calibration:` change `auto_apply_new` in [utils/dynamic_controler.py](utils/dynamic_controler.py)
- `To build a safer demo:` remove or guard the `p`, `k`, and `f` flash paths before handing it to less experienced operators
- `To compare against simpler stereo tools:` use [depth-measurement/stereo-runtime-configuration](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/stereo-runtime-configuration) or [depth-measurement/stereo-on-host](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/stereo-on-host)

## Constraints

- This example can flash calibration data to EEPROM from the keyboard with `p`, `k`, and `f`; treat it as a high-impact workflow.
- Those flash keys are available only in manual mode. Automatic modes never flash; maintain the explicit `flashCalibration=False` even though the SDK default is `True`.
- AutoCalibration 3.11 supports matching native 1280x800 or 640x400 sensor modes; `select_stereo_resolution` rejects incompatible pairs before pipeline start. Stored calibration and sufficient scene texture/coverage are still required.
- It assumes stereo cameras on `CAM_B` and `CAM_C`.
- The overlay and control flow are host-side; this is not a minimal embedded-only calibration demo.
- The current controller defaults `auto_apply_new = True`, so the README key list is slightly misleading: new calibration may already be applied automatically before the operator presses `n`.

## Non-Obvious Repo Conventions

- The main interaction logic lives in the misspelled [utils/dynamic_controler.py](utils/dynamic_controler.py); that filename is intentional in the current repo state.
- Queue objects are created off device nodes and injected into the host controller before `pipeline.start()` so startup results cannot race controller initialization.
- `DynCalib HUD` is an annotation layer over the depth preview, not a separate image source.
- The controller also supports a movable depth HUD ROI using `w/a/s/d` and `z/x`.

## Related Examples

- [depth-measurement/stereo-runtime-configuration](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/stereo-runtime-configuration): use this when you want runtime stereo parameter tuning rather than calibration workflows
- [depth-measurement/stereo-on-host](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/stereo-on-host): use this when you want host-side stereo benchmarking rather than calibration control
- [depth-measurement/calc-spatial-on-host](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/calc-spatial-on-host): use this when you need host-side ROI spatial measurement
- [depth-measurement/wls-filter](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/wls-filter): use this when the host-side focus is disparity filtering instead of calibration state management

## Validation

- `Run:` `python3 main.py`
- `Automatic:` `python3 main.py --mode on-start --device <IP-or-ID>` or `python3 main.py --mode continuous --auto-interval 30 --device <IP-or-ID>`
- `Standalone run:` `oakctl app run .`
- `Success looks like:` the Visualizer shows `Left`, `Right`, `Depth`, and `DynCalib HUD`, and the keyboard commands trigger help, coverage, quality, and calibration-state feedback
- Automatic validation: inspect real stereo/depth frames, HUD status and console JSON; compare confidence before/after any accepted change, verify downstream geometry refresh when parameters change, and compare stored EEPROM before/after. Do not claim improved calibration from a pass that retained existing parameters. Core failure messages report zero confidence fields after retries; use SDK info logs for retry metrics. An unchanged EEPROM is required in automatic mode.
- `Common failure meaning:` the device lacks the required stereo topology, calibration access is failing, or the operator is triggering flash/apply paths without valid calibration state
