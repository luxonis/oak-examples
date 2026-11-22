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

- A color camera on `CAM_A` feeds the person detector with one undistorted output at the model size. That output is also the preview.
- `StereoDepth` on `CAM_B/C` produces metric depth aligned to that undistorted frame. RVC2 links it to `inputAlignTo`. RVC4 uses `ImageAlign` because `StereoDepth` rejects `inputAlignTo` there. This example does not use `dai.node.Depth`.
- `SpatialLocationCalculator` samples that depth inside each person box. The box scale is `0.8` (the old `shrinkingFactor=0.1`), aggregation is the average of every pixel, and depth thresholds are `(200, 30000)` mm. The node runs on device.
- Host nodes derive pairwise distances and a bird’s-eye view from those spatial detections. Those host nodes are unchanged.

## Constraints

- The example requires three cameras and aligned stereo depth.
- The detector frame must stay undistorted. Aligned depth clears distortion coefficients, and on RVC2 the calculator stops unless both streams share that source calibration and the aligned socket.
- It is person-specific; it is not a general spatial-object monitor.
- Distance logic quality depends on reliable depth for each detected person.
- `SpatialLocationCalculator` input queues are blocking and size 1. The calculator and the stereo node are separate streams, so this only pairs them while both emit one message per camera frame.

## Related Examples

- [neural-networks/object-detection/human-machine-safety](https://github.com/luxonis/oak-examples/tree/main/neural-networks/object-detection/human-machine-safety): use this when you need palm-to-object safety logic
- [neural-networks/object-detection/spatial-detections](https://github.com/luxonis/oak-examples/tree/main/neural-networks/object-detection/spatial-detections): use this when you need the general spatial-detection baseline
- [neural-networks/counting/people-counter](https://github.com/luxonis/oak-examples/tree/main/neural-networks/counting/people-counter): use this when you only need a current-frame person count

## Validation

- `Run:` `python3 main.py`
- `Success looks like:` the Visualizer shows people detections, distance annotations, and a bird’s-eye view that updates with scene geometry
- `Common failure meaning:` stereo alignment is poor, the device lacks the required camera set, or the scene does not produce stable person detections
