# AGENTS.md

## Summary

This is the repository reference for matching mismatched camera and NN aspect ratios while preserving as much field of view as possible. Use it when you need the full-FOV resize-mode tutorial rather than just a fixed display-mapping example.

## Use This Example When

- You need to compare crop, stretch, and letterbox strategies.
- You want a runtime-switchable resize-mode demo.
- You need a focused tutorial on image-manip resize behavior before inference.

## Do Not Use This Example When

- You need only one fixed resize mode.
- You need higher-resolution annotation mapping rather than resize-mode switching.
- You need a minimal detector example without resize experimentation.

## Quick Facts

- `Category:` `tutorials/full-fov-nn`
- `Shape:` `multi-entrypoint+standalone`
- `Primary task:` run YOLOv6 on full-FOV camera frames with different resize strategies
- `Entrypoints:` [main.py](main.py), [cropping.py](cropping.py), [letterboxing.py](letterboxing.py), and [stretching.py](stretching.py)
- `Standalone path:` [oakapp.toml](oakapp.toml) packages [main.py](main.py)
- `Frontend:` none
- `Runs on:` RVC2 peripheral, RVC4 peripheral, and RVC4 standalone packaging
- `Requires:` YOLOv6 model assets in [depthai_models/](depthai_models/)
- `Input:` live `CAM_A`
- `Output:` Visualizer topics such as `Resized`, `Visualizations`, and `Resize mode`
- `Models:` YOLOv6 YAMLs in [depthai_models/](depthai_models/)
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [cropping.py](cropping.py)
- [letterboxing.py](letterboxing.py)
- [stretching.py](stretching.py)
- [utils/resize_controller.py](utils/resize_controller.py)
- [oakapp.toml](oakapp.toml)

## Architecture

- [main.py](main.py) captures a large `3000x2000` stream and pushes resize-mode changes into `ImageManip` at runtime through [utils/resize_controller.py](utils/resize_controller.py).
- The fixed-mode scripts use `812x608` input and hardcode one resize mode each.
- All variants feed the resized branch into YOLOv6 and publish the NN passthrough frame plus detection overlays.
- [combine_outputs.py](combine_outputs.py) exists as an extra helper/example artifact, but [main.py](main.py) does not use it in the current repo state.

## Constraints

- The current code keybindings in [utils/resize_controller.py](utils/resize_controller.py) are `a -> LETTERBOX`, `s -> STRETCH`, and `d -> CENTER_CROP`, which does not match the README’s mode descriptions.
- [oakapp.toml](oakapp.toml) only packages [main.py](main.py), not the fixed-mode scripts.
- This tutorial is about resize tradeoffs, so some modes intentionally distort or crop the source frame.

## Related Examples

- [tutorials/display-detections](https://github.com/luxonis/oak-examples/tree/main/tutorials/display-detections): use this when you need display-mapping strategies instead of resize-mode switching
- [neural-networks/generic-example](https://github.com/luxonis/oak-examples/tree/main/neural-networks/generic-example): use this when you need the basic single-model detector scaffold
- [tutorials/camera-demo](https://github.com/luxonis/oak-examples/tree/main/tutorials/camera-demo): use this when you need a camera baseline without any NN resize logic

## Validation

- `Interactive mode:` `python3 main.py`
- `Fixed crop mode:` `python3 cropping.py`
- `Success looks like:` the Visualizer shows resize-mode changes affecting the detection view, and the fixed-mode scripts each stay in their declared strategy
- `Common failure meaning:` the README keybinding text was trusted over the current code, or the user expects a generic detector example rather than a resize-technique tutorial
