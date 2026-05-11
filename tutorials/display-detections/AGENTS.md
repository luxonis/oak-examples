# AGENTS.md

## Summary

This is the repository reference for three different strategies for drawing detections on something larger than the NN input frame. Use it when you need to reason about how annotations map between inference frames and display frames.

## Use This Example When

- You need a tutorial about higher-resolution display of NN detections.
- You want to compare passthrough, crop-translate, and stretch-before-inference strategies.
- You need a small folder with multiple entrypoints that each isolate one mapping technique.

## Do Not Use This Example When

- You need a single packaged app that exposes all three modes interactively.
- You need full-FOV runtime mode switching rather than fixed scripts.
- You need a generic detector baseline without display-mapping concerns.

## Quick Facts

- `Category:` `tutorials/display-detections`
- `Shape:` `multi-entrypoint+standalone`
- `Primary task:` show how to align detections with different display-frame choices
- `Entrypoints:` [passthrough.py](passthrough.py), [crop_highres.py](crop_highres.py), and [stretch_before_inferencing.py](stretch_before_inferencing.py)
- `Standalone path:` [oakapp.toml](oakapp.toml) packages [passthrough.py](passthrough.py)
- `Frontend:` none
- `Runs on:` RVC2 peripheral, RVC4 peripheral, and RVC4 standalone packaging
- `Requires:` YOLOv6 model assets in [depthai_models/](depthai_models/)
- `Input:` live `CAM_A`
- `Output:` Visualizer topics that vary by script
- `Models:` YOLOv6 YAMLs in [depthai_models/](depthai_models/)
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md)
- [passthrough.py](passthrough.py)
- [crop_highres.py](crop_highres.py)
- [stretch_before_inferencing.py](stretch_before_inferencing.py)
- [utils/translate_cropped_detections.py](utils/translate_cropped_detections.py)
- [oakapp.toml](oakapp.toml)

## Architecture

- [passthrough.py](passthrough.py) displays the detector’s passthrough frame directly, so annotations stay naturally aligned with the NN input.
- [crop_highres.py](crop_highres.py) runs the detector on a cropped `512x288` region from a `640x480` frame, then uses [utils/translate_cropped_detections.py](utils/translate_cropped_detections.py) to map detections back into the larger frame space.
- [stretch_before_inferencing.py](stretch_before_inferencing.py) keeps a `1920x1440` full view while a stretched `512x288` branch feeds inference.
- All three scripts use the same YOLOv6 model family and publish their visual comparison through the DepthAI Visualizer.

## Constraints

- [oakapp.toml](oakapp.toml) only packages [passthrough.py](passthrough.py), not the other tutorial variants.
- [passthrough.py](passthrough.py) and [stretch_before_inferencing.py](stretch_before_inferencing.py) both apply a host-side `FilterDets` that removes raw label `57`.
- This folder is about annotation/display alignment, not about maximizing detector quality.

## Related Examples

- [../full-fov-nn](../full-fov-nn/): use this when you need a broader resize-technique tutorial with runtime switching
- [../../neural-networks/generic-example](../../neural-networks/generic-example/): use this when you need the simpler detector scaffold
- [../../neural-networks/object-detection/yolo-host-decoding](../../neural-networks/object-detection/yolo-host-decoding/): use this when the main concern is YOLO host decoding rather than display mapping

## Validation

- `Passthrough:` `python3 passthrough.py`
- `Crop mapping:` `python3 crop_highres.py`
- `Success looks like:` the Visualizer clearly shows how each script aligns detections to its chosen display frame
- `Common failure meaning:` the user assumes all three modes are packaged by default, or expects this folder to be about model accuracy instead of coordinate/display translation
