# AGENTS.md

## Summary

This is the repository reference for the simplest multi-sensor camera preview tutorial. Use it when you need a baseline that publishes every connected camera stream with minimal processing.

## Use This Example When

- You need a minimal camera-preview tutorial.
- You want to see every connected camera sensor on one device.
- You need a simple encoded-stream reference without inference.

## Do Not Use This Example When

- You need stereo depth rather than raw camera previews.
- You need per-sensor custom resolutions or per-sensor logic.
- You need host-side OpenCV processing instead of Visualizer topics.

## Quick Facts

- `Category:` `tutorials/camera-demo`
- `Shape:` `script+standalone-service`
- `Primary task:` stream every connected camera sensor to the Visualizer
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [backend-run.sh](backend-run.sh) and [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` RVC2 peripheral, RVC4 peripheral, and RVC4 standalone packaging
- `Requires:` at least one connected camera sensor
- `Input:` all connected device sensors discovered at runtime
- `Output:` one Visualizer topic per sensor socket name
- `Models:` none
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [utils/arguments.py](utils/arguments.py)
- [backend-run.sh](backend-run.sh)
- [oakapp.toml](oakapp.toml)

## Architecture

- [main.py](main.py) enumerates `device.getConnectedCameraFeatures()` and creates one `dai.node.Camera` per sensor.
- Each sensor output is capped at `1920x1080` if the native resolution is larger.
- Every stream is encoded as `H264_MAIN` before being sent to the Visualizer.
- Topic names are the raw socket names such as `CAM_A`, `CAM_B`, and `CAM_C`.

## Constraints

- This tutorial always publishes all discovered sensors; there is no CLI to select a subset.
- High-resolution sensors are intentionally limited to `1080p` in [main.py](main.py).
- The output is optimized for Visualizer preview, not for file recording or custom host processing.

## Related Examples

- [tutorials/camera-depth](https://github.com/luxonis/oak-examples/tree/main/tutorials/camera-depth): use this when you need stereo depth instead of plain previews
- [tutorials/play-encoded-stream](https://github.com/luxonis/oak-examples/tree/main/tutorials/play-encoded-stream): use this when you want to focus on encoded video playback paths
- [streaming/on-device-encoding](https://github.com/luxonis/oak-examples/tree/main/streaming/on-device-encoding): use this when you need encoded recording rather than live preview topics

## Validation

- `Run:` `python3 main.py`
- `Success looks like:` the Visualizer shows one topic per connected sensor and all streams respond to `q`
- `Common failure meaning:` the device has no usable camera sensors, the user expects only `CAM_A`, or the encoded preview path is mistaken for a raw host-processing example
