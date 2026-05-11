# AGENTS.md

## Summary

This is the repository reference for the simplest host-side multi-device orchestration patterns. Use it when you need a baseline for discovering multiple OAKs and starting one pipeline per device.

## Use This Example When

- You need a host-only multiple-device starter.
- You want to compare plain preview, per-device detection, and per-device encoded streaming.
- You need examples that all share the same discovery/filtering helpers.

## Do Not Use This Example When

- You need shared-world calibration or 3D fusion.
- You need a packaged standalone app.
- You need stitched imagery across devices rather than one pipeline per device.

## Quick Facts

- `Category:` `tutorials/multiple-devices/multiple-devices-preview`
- `Shape:` `multi-entrypoint+multi-device-host`
- `Primary task:` discover multiple devices and run one simple pipeline per device
- `Entrypoints:` [main.py](main.py), [multi-device-yolov6.py](multi-device-yolov6.py), and [multi-device-encoding.py](multi-device-encoding.py)
- `Standalone path:` none
- `Frontend:` none
- `Runs on:` host mode only, with one or more discoverable DepthAI devices
- `Requires:` multiple devices only if you want the full point of the tutorial; IP devices are optional via CLI
- `Input:` live `CAM_A` from each configured device
- `Output:` Visualizer topics grouped per device
- `Models:` YOLOv6 model-zoo slug in [multi-device-yolov6.py](multi-device-yolov6.py); none for the other entrypoints
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [multi-device-yolov6.py](multi-device-yolov6.py)
- [multi-device-encoding.py](multi-device-encoding.py)
- [utils/utility.py](utils/utility.py)
- [utils/arguments.py](utils/arguments.py)

## Architecture

- [main.py](main.py) is the plainest version: it publishes a `640x400` `CAM_A` preview per device.
- [multi-device-yolov6.py](multi-device-yolov6.py) adds one detector pipeline per device and publishes both preview and annotation topics grouped by MXID.
- [multi-device-encoding.py](multi-device-encoding.py) publishes encoded H.264 streams per device for Visualizer playback.
- All three entrypoints rely on the same device filtering, setup, and start helpers in [utils/utility.py](utils/utility.py).

## Constraints

- These are host-only examples; there is no `oakapp.toml` path here.
- Every entrypoint uses `CAM_A` only.
- Despite helper naming and some print strings, [multi-device-encoding.py](multi-device-encoding.py) actually builds `H264_MAIN` streams, not MJPEG.
- [multi-device-yolov6.py](multi-device-yolov6.py) hardcodes the model slug `luxonis/yolov6-nano:r2-coco-512x288`.

## Related Examples

- [../multi-cam-calibration](../multi-cam-calibration/): use this when the next step is world-frame calibration
- [../spatial-detection-fusion](../spatial-detection-fusion/): use this when multiple devices should collaborate in 3D space
- [../multiple-device-stitch-nn](../multiple-device-stitch-nn/): use this when multiple devices should be stitched into one panorama-like view

## Validation

- `Preview:` `python3 main.py`
- `Detections:` `python3 multi-device-yolov6.py`
- `Success looks like:` the Visualizer shows one group of topics per discovered device and `q` exits cleanly
- `Common failure meaning:` no devices were discovered after filtering, the user expected a shared fused output, or the encoding script was assumed to be MJPEG because of helper names instead of the current code
