# AGENTS.md

## Summary

Automatic runtime stereo calibration with on-start or continuous operation, live camera/depth previews, and a status HUD. Use this as the small AutoCalibration reference alongside the separate manual DynamicCalibration example.

## Use This Example When

- You need a reference for `dai.node.AutoCalibration` with native validation and retries.
- You want automatic runtime updates and visible confidence/status without copying the manual calibration controller.
- You need a host script with an RVC4 standalone packaging path.

## Do Not Use This Example When

- You need manual coverage/quality checks, apply/revert controls, or EEPROM flashing.
- Your stereo sensors lack matching native 1280x800 or 640x400 modes.
- You need ToF, external calibration targets, or multi-device extrinsics.

## Quick Facts

- `Category:` `depth-measurement/auto-calibration`
- `Shape:` `script+standalone`
- `Primary task:` automatic runtime stereo calibration
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` RVC2 peripheral and RVC4 peripheral/standalone with a supported stereo pair
- `Requires:` stored calibration, matching native 1280x800 or 640x400 modes on `CAM_B/C`, and scene texture/coverage
- `Input:` stereo camera ISP streams
- `Output:` `Left`, `Right`, `Depth`, `AutoCalib HUD`, and console JSON results
- `Models:` none
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md): modes, acceptance rules, and runtime-only calibration behavior.
- [main.py](main.py): stereo/AutoCalibration pipeline and visualization setup.
- [utils/arguments.py](utils/arguments.py): CLI options; on-start is the default.
- [utils/camera.py](utils/camera.py): compatible native sensor-mode selection.
- [utils/auto_calibration_status.py](utils/auto_calibration_status.py): result consumption, console JSON, and status annotations.
- [oakapp.toml](oakapp.toml): independent application identifier and packaging entrypoint.

## Architecture

- Cameras on `CAM_B/C` are built with matching supported native sensor modes and feed `StereoDepth` for live previews.
- One explicit `AutoCalibration` node owns its internal DynamicCalibration worker and samples the same cameras' unrectified ISP streams.
- `flashCalibration=False` overrides the SDK's persistent-write default. The pipeline's implicit AutoCalibration mode is `OFF`.
- Native confidence thresholds, validation-set size, and retry limits remain enabled. Only mode and continuous-cycle pause are configured here.
- `ApplyDepthColormap` colorizes disparity. `AutoCalibrationStatus` consumes native results and emits annotations timestamped to that preview, alongside JSON logs.
- The status node never applies calibration: the SDK handles accepted runtime updates. A pass may retain existing parameters.

## Data Flow

- `CAM_B/C -> StereoDepth -> Left/Right + disparity -> ApplyDepthColormap -> Depth`
- `Camera ISP -> AutoCalibration -> result input -> AutoCalibrationStatus -> AutoCalib HUD + console JSON`
- `Visualizer q -> clean pipeline shutdown`

## Constraints

- This example must never flash EEPROM or deliberately alter initial calibration. Keep the explicit `flashCalibration=False`.
- AutoCalibration 3.11 supports matching native 1280x800 or 640x400 sensor modes; reject incompatible pairs before starting.
- `AutoCalibrationResult` cannot be published directly through RemoteConnection in DepthAI 3.11. Inspect the HUD annotations or console JSON.
- A failed cycle retains the active calibration. Final failure messages have zero confidence fields; SDK info logs contain retry metrics.
- The HUD displays the latest completed result while subsequent continuous cycles run.
- Runtime updates are temporary. Manual controls and persistence belong to the separate DynamicCalibration example.

## Related Examples

- [Dynamic Calibration](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/dynamic-calibration): full manual calibration diagnostics, apply/revert, and explicit flash controls.
- [Stereo Runtime Configuration](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/stereo-runtime-configuration): runtime stereo matching controls.

## Validation

- `Run:` `python3 main.py --device <IP-or-ID>` for on-start mode; add `--mode continuous --auto-interval 30` for repeated cycles.
- `Standalone run:` `oakctl app run . -d <IP-or-ID>`; startup must print `Pipeline started.`.
- `Success looks like:` live camera/disparity views and `AutoCalib HUD` status/confidence after a native cycle completes.
- Inspect real frames, HUD messages, and the pipeline graph with `oakctl inspect`; verify exactly one automatic controller and its internal worker.
- Compare stored EEPROM before/after automatic runs. A successful validation alone does not prove improved calibration or geometry refresh after changed parameters; validate those claims when a natural accepted change occurs.
