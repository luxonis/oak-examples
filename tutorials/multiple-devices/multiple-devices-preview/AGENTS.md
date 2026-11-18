# AGENTS.md

## Summary

This is the repository reference for the simplest multi-device pipeline patterns. Use it when you need a baseline for running one DepthAI pipeline across multiple OAKs with nodes placed on each device.

## Use This Example When

- You need a host-only multiple-device starter.
- You want to compare plain preview, per-device detection, and per-device encoded streaming.
- You need the minimal `pipeline.addDevice` plus `pipeline.create(node, device)` pattern.

## Do Not Use This Example When

- You need cross-device calibration or 3D fusion.
- You need a packaged standalone app.
- You need stitched imagery across devices rather than independent streams per device.

## Quick Facts

- `Category:` `tutorials/multiple-devices/multiple-devices-preview`
- `Shape:` `multi-entrypoint+multi-device-host`
- `Primary task:` run one pipeline across multiple devices with a simple per-device branch
- `Entrypoints:` [main.py](main.py), [multi-device-yolov6.py](multi-device-yolov6.py), and [multi-device-encoding.py](multi-device-encoding.py)
- `Standalone path:` none
- `Frontend:` none
- `Runs on:` host mode only, with one or more DepthAI devices
- `Requires:` multiple devices only if you want the full point of the tutorial; IP devices via `--devices` or `--include-ip`
- `Input:` live `CAM_A` from each configured device
- `Output:` Visualizer topics per device
- `Models:` YOLOv6 model-zoo slug in [multi-device-yolov6.py](multi-device-yolov6.py); none for the other entrypoints
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md)
- [utils/utility.py](utils/utility.py)
- [main.py](main.py)
- [multi-device-yolov6.py](multi-device-yolov6.py)
- [multi-device-encoding.py](multi-device-encoding.py)
- [utils/arguments.py](utils/arguments.py)

## Architecture

- [utils/utility.py](utils/utility.py) builds one `dai.Pipeline(createImplicitDevice=False)`, adds each device with `pipeline.addDevice`, calls the entrypoint's per-device setup function, then starts the single pipeline.
- [main.py](main.py) is the plainest version: it publishes a `640x400` `CAM_A` preview per device.
- [multi-device-yolov6.py](multi-device-yolov6.py) creates a native `DetectionNetwork` on each device and publishes passthrough and detection topics grouped by device ID.
- [multi-device-encoding.py](multi-device-encoding.py) creates a `VideoEncoder` on each device and publishes the H.264 streams for Visualizer playback.

## Constraints

- These are host-only examples; there is no `oakapp.toml` path here.
- Every entrypoint uses `CAM_A` only.
- Discovery skips IP-only devices unless `--include-ip` is set; `--devices` selects devices explicitly.
- [multi-device-encoding.py](multi-device-encoding.py) builds `H264_MAIN` streams.
- [multi-device-yolov6.py](multi-device-yolov6.py) hardcodes the model slug `luxonis/yolov6-nano:r2-coco-512x288`.
- The multi-device pipeline API requires `depthai>=3.12`.

## Related Examples

- [tutorials/multiple-devices/multi-device-calibration](https://github.com/luxonis/oak-examples/tree/main/tutorials/multiple-devices/multi-device-calibration): use this when the next step is cross-device calibration
- [tutorials/multiple-devices/spatial-detection-fusion](https://github.com/luxonis/oak-examples/tree/main/tutorials/multiple-devices/spatial-detection-fusion): use this when multiple devices should collaborate in 3D space
- [tutorials/multiple-devices/multiple-device-stitch-nn](https://github.com/luxonis/oak-examples/tree/main/tutorials/multiple-devices/multiple-device-stitch-nn): use this when multiple devices should be stitched into one panorama-like view
- [tutorials/multiple-devices/multi-device-point-cloud](https://github.com/luxonis/oak-examples/tree/main/tutorials/multiple-devices/multi-device-point-cloud): merged 3D point cloud of calibrated devices
- [tutorials/multiple-devices/multi-device-panorama](https://github.com/luxonis/oak-examples/tree/main/tutorials/multiple-devices/multi-device-panorama): calibrated panorama of all devices
- [tutorials/multiple-devices/multi-device-birds-eye-view](https://github.com/luxonis/oak-examples/tree/main/tutorials/multiple-devices/multi-device-birds-eye-view): top-down ground view of calibrated devices

## Validation

- `Preview:` `python3 main.py`
- `Detections:` `python3 multi-device-yolov6.py`
- `Success looks like:` the Visualizer shows the topics of every selected device and `q` exits cleanly
- `Common failure meaning:` no devices were discovered after filtering (IP devices need `--include-ip` or `--devices`), or the user expected a shared fused output
