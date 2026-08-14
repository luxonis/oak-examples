# AGENTS.md

## Summary

This is the repository reference for person detection plus distance monitoring. Use it when you need person-to-person spacing logic on top of stereo-aligned detections.

## Use This Example When

- You need social-distance or proximity monitoring.
- You want a bird’s-eye view derived from depth.
- You need a person-specific spatial detection baseline rather than a generic detector.

## Do Not Use This Example When

- You need general object spatial detections.
- You need hand-to-object safety logic instead of person-to-person distance.
- You need a pure RGB detector with no stereo branch.

## Quick Facts

- `Category:` `neural-networks/object-detection/social-distancing`
- `Shape:` `script+standalone`
- `Primary task:` detect people and monitor their pairwise distance
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` devices with `CAM_A`, `CAM_B`, and `CAM_C`; RVC2 peripheral, RVC4 peripheral, and RVC4 standalone packaging
- `Requires:` SCRFD person detector, depth, and calibration
- `Input:` live color and stereo pair
- `Output:` `Video`, `Detections`, `Distances`, and `Bird-eye view`
- `Models:` SCRFD person-detection YAMLs in [depthai_models/](depthai_models/)
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [utils/measure_object_distance.py](utils/measure_object_distance.py)
- [utils/host_social_distancing.py](utils/host_social_distancing.py)
- [utils/host_bird_eye_view.py](utils/host_bird_eye_view.py)

## Architecture

- A color camera on `CAM_A` feeds the person detector.
- `Depth` owns depth-source selection and aligns depth back to the RGB stream.
- `DepthMerger` attaches depth to the 2D person detections.
- Host nodes derive pairwise distances and a bird’s-eye view from those spatial detections.

## Constraints

- The example requires three cameras and aligned depth.
- It is person-specific; it is not a general spatial-object monitor.
- Distance logic quality depends on reliable depth for each detected person.

## Related Examples

- [neural-networks/object-detection/human-machine-safety](https://github.com/luxonis/oak-examples/tree/main/neural-networks/object-detection/human-machine-safety): use this when you need palm-to-object safety logic
- [neural-networks/object-detection/spatial-detections](https://github.com/luxonis/oak-examples/tree/main/neural-networks/object-detection/spatial-detections): use this when you need the general spatial-detection baseline
- [neural-networks/counting/people-counter](https://github.com/luxonis/oak-examples/tree/main/neural-networks/counting/people-counter): use this when you only need a current-frame person count

## Validation

- `Run:` `python3 main.py`
- `Success looks like:` the Visualizer shows people detections, distance annotations, and a bird’s-eye view that updates with scene geometry
- `Common failure meaning:` stereo alignment is poor, the device lacks the required camera set, or the scene does not produce stable person detections
