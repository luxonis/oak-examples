# AGENTS.md

## Summary

This is the repository reference for the most minimal unified-depth tutorial in the repo. Use it when you need a compact color-plus-depth baseline without a neural network.

## Use This Example When

- You need a simple stereo pipeline.
- You want color, left, right, and metric-depth output together.
- You need a minimal starting point before adding spatial logic.

## Do Not Use This Example When

- You need only camera previews.
- You need object detections or spatial detections.
- You need a ToF-specific tuning or point-cloud workflow instead of a compact depth baseline.

## Quick Facts

- `Category:` `tutorials/camera-depth`
- `Shape:` `script+standalone-service`
- `Primary task:` build a minimal unified-depth pipeline with visual outputs
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` devices with `CAM_A`, `CAM_B`, and `CAM_C`; RVC2 peripheral, RVC4 peripheral, and RVC4 standalone packaging
- `Requires:` stereo-capable hardware and calibration
- `Input:` live color plus stereo pair
- `Output:` `Color`, `Depth`, `Left`, and `Right`
- `Models:` none
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [utils/arguments.py](utils/arguments.py)
- [oakapp.toml](oakapp.toml)

## Architecture

- [main.py](main.py) creates `CAM_A` for color and `CAM_B/C` for stereo.
- `dai.node.Depth` is built with `AUTO` backend selection and a `640x480` size request.
- `ApplyDepthColormap` colorizes depth for display.
- The color preview is H.264 encoded before being published to the Visualizer.

## Constraints

- The `Depth` topic is a colorized metric-depth visualization.
- The left and right topics are still camera previews; they are not manually wired into a concrete stereo backend.
- The color output is fixed to `1920x1080`, while the stereo pair is fixed to `640x480`.

## Related Examples

- [tutorials/camera-demo](https://github.com/luxonis/oak-examples/tree/main/tutorials/camera-demo): use this when you only need multi-sensor previews
- [depth-measurement/calc-spatial-on-host](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/calc-spatial-on-host): use this when you need host-side spatial ROI computation
- [neural-networks/object-detection/spatial-detections](https://github.com/luxonis/oak-examples/tree/main/neural-networks/object-detection/spatial-detections): use this when you need depth-backed detections instead of a raw depth view

## Validation

- `Run:` `python3 main.py`
- `Success looks like:` the Visualizer shows `Color`, `Depth`, `Left`, and `Right`, and the depth view changes with scene geometry
- `Common failure meaning:` the device does not expose a supported depth source, calibration is unavailable, or the requested depth backend cannot satisfy the selected size/FPS
