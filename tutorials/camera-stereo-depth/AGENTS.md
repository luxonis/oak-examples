# AGENTS.md

## Summary

This is the repository reference for the most minimal stereo-depth tutorial in the repo. Use it when you need a compact color-plus-stereo baseline without a neural network.

## Use This Example When

- You need a simple stereo pipeline.
- You want color, left, right, and disparity-style output together.
- You need a minimal starting point before adding spatial logic.

## Do Not Use This Example When

- You need only camera previews.
- You need object detections or spatial detections.
- You need a ToF or point-cloud workflow instead of stereo disparity.

## Quick Facts

- `Category:` `tutorials/camera-stereo-depth`
- `Shape:` `script+standalone-service`
- `Primary task:` build a minimal stereo-depth pipeline with visual outputs
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [backend-run.sh](backend-run.sh) and [oakapp.toml](oakapp.toml)
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
- [backend-run.sh](backend-run.sh)
- [oakapp.toml](oakapp.toml)

## Architecture

- [main.py](main.py) creates `CAM_A` for color and `CAM_B/C` for stereo.
- `dai.node.StereoDepth` is built from `640x480` left/right outputs.
- `ApplyDepthColormap` colorizes `stereo.disparity` for display.
- The color preview is H.264 encoded before being published to the Visualizer.

## Constraints

- The `Depth` topic is a colorized disparity visualization, not a raw metric-depth stream.
- `StereoDepth` is configured with rectification, left-right check, and extended disparity in [main.py](main.py).
- The color output is fixed to `1920x1080`, while the stereo pair is fixed to `640x480`.

## Related Examples

- [../camera-demo](../camera-demo/): use this when you only need multi-sensor previews
- [../../depth-measurement/calc-spatial-on-host](../../depth-measurement/calc-spatial-on-host/): use this when you need host-side spatial ROI computation
- [../../neural-networks/object-detection/spatial-detections](../../neural-networks/object-detection/spatial-detections/): use this when you need stereo-backed detections instead of raw disparity

## Validation

- `Run:` `python3 main.py`
- `Success looks like:` the Visualizer shows `Color`, `Depth`, `Left`, and `Right`, and the depth view changes with scene geometry
- `Common failure meaning:` the device does not expose `CAM_B/C`, stereo calibration is unavailable, or the user expects metric depth instead of a colormapped disparity tutorial
