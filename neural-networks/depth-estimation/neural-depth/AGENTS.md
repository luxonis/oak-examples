# AGENTS.md

## Summary

This is the repository reference for Luxonis `NeuralDepth` running directly on RVC4 hardware. Use it when you need the built-in NeuralDepth node and its runtime controls rather than a host-run stereo model.

## Use This Example When

- You need `dai.node.NeuralDepth`.
- You want to inspect disparity, confidence, and edge outputs together.
- You need keyboard-driven runtime control over the node configuration.

## Do Not Use This Example When

- You need RVC2 compatibility.
- You need host-side stereo model comparison.
- You need dataset evaluation rather than live camera output.

## Quick Facts

- `Category:` `neural-networks/depth-estimation/neural-depth`
- `Shape:` `script+standalone`
- `Primary task:` run Luxonis NeuralDepth live on device
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` RVC4 only
- `Requires:` stereo mono pair on `CAM_B/C`
- `Input:` full-resolution stereo camera pair
- `Output:` `Disparity`, `Confidence`, `Edge`, and `Controls`
- `Models:` `NeuralDepth` device-zoo models selected through `--model`
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [utils/manual_camera_control.py](utils/manual_camera_control.py)
- [utils/arguments.py](utils/arguments.py)
- [oakapp.toml](oakapp.toml)

## Architecture

- Two full-resolution mono camera outputs feed `dai.node.NeuralDepth`.
- [utils/manual_camera_control.py](utils/manual_camera_control.py) owns the runtime config input queue and keyboard control overlay.
- `ApplyDepthColormap` visualizes disparity, while `ApplyColormap` visualizes confidence and edge outputs.

## Constraints

- [main.py](main.py) explicitly raises on non-RVC4 platforms.
- This example is live-camera only; there is no replay input path.
- Runtime behavior depends on the control bindings implemented in [utils/manual_camera_control.py](utils/manual_camera_control.py).

## Related Examples

- [../crestereo-stereo-matching](../crestereo-stereo-matching/): use this when you want another on-device neural stereo baseline
- [host_eval](host_eval/): use this when you need offline dataset evaluation for NeuralDepth
- [../../../depth-measurement/stereo-runtime-configuration](../../../depth-measurement/stereo-runtime-configuration/): use this when you want runtime stereo controls for classic `StereoDepth`

## Validation

- `Run:` `python3 main.py`
- `Success looks like:` the Visualizer shows `Disparity`, `Confidence`, `Edge`, and `Controls`, and keyboard input updates the control overlay
- `Common failure meaning:` the device is not RVC4, stereo cameras are unavailable, or the chosen NeuralDepth model is incompatible with the hardware
