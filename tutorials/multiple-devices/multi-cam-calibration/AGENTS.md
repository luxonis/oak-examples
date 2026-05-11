# AGENTS.md

## Summary

This is the repository reference for generating per-device extrinsic calibration files across multiple OAK cameras. Use it when another multi-device example needs all cameras expressed in a shared world frame.

## Use This Example When

- You need extrinsic calibration files for multiple devices.
- You want a host-driven checkerboard capture workflow.
- You plan to use [../spatial-detection-fusion](../spatial-detection-fusion/) or another multi-camera world-frame application.

## Do Not Use This Example When

- You only need a preview of multiple devices.
- You need a packaged standalone app.
- You need intrinsic calibration or stereo calibration rather than world-frame extrinsics.

## Quick Facts

- `Category:` `tutorials/multiple-devices/multi-cam-calibration`
- `Shape:` `multi-device-host`
- `Primary task:` capture checkerboard stills and estimate per-device extrinsics
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` none
- `Frontend:` none
- `Runs on:` host mode only, with one or more discoverable DepthAI devices
- `Requires:` checkerboard target, host OpenCV stack, and writable output directory
- `Input:` live `CAM_A` preview plus on-demand still captures
- `Output:` `calibration_data/extrinsics_<MXID>.npz` files and calibration annotations in the Visualizer
- `Models:` none
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [utils/calibration_node.py](utils/calibration_node.py)
- [utils/utility.py](utils/utility.py)
- [utils/arguments.py](utils/arguments.py)
- [pattern.pdf](pattern.pdf)

## Architecture

- [main.py](main.py) discovers multiple devices, creates one pipeline per device, and cycles calibration focus with keyboard input.
- [utils/calibration_node.py](utils/calibration_node.py) requests a `3840x2160` still, finds checkerboard corners, runs `solvePnP`, and saves the resulting transforms.
- The saved outputs include `world_to_cam`, `cam_to_world`, the original `rvec` and `tvec`, and the still-image intrinsics used for the solve.
- [pattern.pdf](pattern.pdf) matches the default checkerboard configuration declared in [utils/calibration_node.py](utils/calibration_node.py).

## Constraints

- This tutorial calibrates `CAM_A` only.
- The checkerboard parameters and output folder are hardcoded in [utils/calibration_node.py](utils/calibration_node.py) via `config`.
- Output files are written relative to the current working directory into `calibration_data/`.
- With multiple devices, the Visualizer grouping can make `Selected for Calib` annotations look confusing, as the README notes.

## Related Examples

- [../spatial-detection-fusion](../spatial-detection-fusion/): use this after calibration when you need fused 3D detections
- [../multiple-devices-preview](../multiple-devices-preview/): use this when you only need multi-device preview/orchestration
- [../../camera-stereo-depth](../../camera-stereo-depth/): use this when you need a single-device stereo baseline rather than multi-device world calibration

## Validation

- `Run:` `python3 main.py`
- `Controls:` press `a` to change the selected device and `c` to capture/calibrate
- `Success looks like:` terminal output reports successful pose estimation and `calibration_data/extrinsics_<MXID>.npz` files appear
- `Common failure meaning:` the checkerboard pattern or sizing does not match the configured values, still capture times out, or the user expects a packaged standalone flow
