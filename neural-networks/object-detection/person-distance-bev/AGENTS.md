# AGENTS.md

## Summary

Visualize camera-relative person positions in a bird's-eye view and measure pairwise 3D distances from depth-aligned detections. Use this as a person-distance visualization reference, not an alerting app.

## Use This Example When

- You want a camera-relative X/Z view of detected people.
- You need a simple example of measuring and displaying pairwise 3D detection distances.
- You want to inspect person positions and distances with the standard DepthAI Visualizer.

## Do Not Use This Example When

- You need machine-mounted person proximity zones and alerts; use `apps/machine-pov-proximity-alert`.
- You need general object spatial detections; use `spatial-detections`.
- You need a floor-aligned map, calibrated world coordinates, or a pure RGB detector.

## Quick Facts

- `Category:` `neural-networks/object-detection/person-distance-bev`
- `Shape:` `script+standalone`
- `Primary task:` display person positions and pairwise 3D distances
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` devices with a color camera and `Depth.Algorithm.AUTO` support; RVC2 peripheral, RVC4 peripheral, and RVC4 standalone packaging
- `Requires:` SCRFD person detector, depth, and calibration
- `Input:` live color and an automatically selected depth source
- `Output:` `Video`, `Detections`, `Pairwise distances`, and `Bird's-eye view`
- `Models:` SCRFD person detection YAMLs in [depthai_models/](depthai_models/)
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [utils/measure_object_distance.py](utils/measure_object_distance.py)
- [utils/host_distance_annotations.py](utils/host_distance_annotations.py)
- [utils/host_bird_eye_view.py](utils/host_bird_eye_view.py)

## Architecture

- A color camera on `CAM_A` feeds the SCRFD person detector.
- `Depth.Algorithm.AUTO` selects the device's depth backend; `setAlignTo(rgb)` aligns its output to the color stream.
- `DepthMerger` attaches depth to the 2D person detections.
- `MeasureObjectDistance` filters invalid coordinates and computes every pair's 3D Euclidean distance.
- `DistanceAnnotations` displays all pair distances on the camera image. `BirdsEyeView` plots person positions on a 960 × 720 camera-relative X/Z view, with only the closest visible pair connected and its 3D distance in the header.

## Constraints

- The example requires a color camera, a supported depth backend, and calibration for spatial coordinates.
- On RVC2, the SCRFD archive is compiled for 7 SHAVEs so it fits alongside depth and image processing.
- The example does not implement a distance threshold or alert.
- The X/Z view is not floor-aligned; camera tilt changes its meaning. The displayed labels are 3D X/Y/Z distances, not distances measured on the 2D plot.
- The view displays X within ±7.5 m and Z within 0–15 m. Invalid spatial coordinates are excluded from both views.
- The bird's-eye view draws only the closest visible pair connection; the camera-image annotations still show every pair.

## Related Examples

- [apps/machine-pov-proximity-alert](https://github.com/luxonis/oak-examples/tree/main/apps/machine-pov-proximity-alert): use this for machine-mounted person proximity zones and alerts
- [neural-networks/object-detection/spatial-detections](https://github.com/luxonis/oak-examples/tree/main/neural-networks/object-detection/spatial-detections): use this when you need the general spatial-detection baseline
- [neural-networks/counting/people-counter](https://github.com/luxonis/oak-examples/tree/main/neural-networks/counting/people-counter): use this when you only need a current-frame person count

## Validation

- `Run:` `python3 main.py`
- `Success looks like:` the Visualizer shows person detections, pairwise distance annotations, and a camera-relative bird's-eye view with person markers and the closest visible pair highlighted
- `Common failure meaning:` depth alignment or calibration is poor, the device lacks a compatible depth backend, or the scene does not produce stable person detections
