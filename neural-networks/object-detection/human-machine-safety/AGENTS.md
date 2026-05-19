# AGENTS.md

## Summary

This is the repository reference for distance-based safety checks between detected palms and selected dangerous objects. Use it when you need multi-model detection fused with stereo depth and host-side alert logic.

## Use This Example When

- You need multi-model safety logic with spatial measurements.
- You want to detect palms and dangerous objects in the same frame.
- You need a stereo-aligned RGB workflow with alert overlays.

## Do Not Use This Example When

- You only need generic spatial detections.
- You need person-to-person distance monitoring instead of hand-to-object safety.
- You need a single-model detector with no stereo branch.

## Quick Facts

- `Category:` `neural-networks/object-detection/human-machine-safety`
- `Shape:` `script+standalone`
- `Primary task:` detect palms and dangerous objects and measure their distance
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` devices with `CAM_A`, `CAM_B`, and `CAM_C`; RVC2 peripheral, RVC4 peripheral, and RVC4 standalone packaging
- `Requires:` stereo depth, palm detector, object detector, and calibration
- `Input:` live color plus stereo pair
- `Output:` `Color`, `Detections`, `Distances`, and `Alert`
- `Models:` YOLOv6 and MediaPipe palm YAMLs in [depthai_models/](depthai_models/)
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [utils/detection_merger.py](utils/detection_merger.py)
- [utils/measure_object_distance.py](utils/measure_object_distance.py)
- [utils/show_alert.py](utils/show_alert.py)
- [utils/visualize_object_distances.py](utils/visualize_object_distances.py)

## Architecture

- The color stream on `CAM_A` feeds both object detection and palm detection.
- Stereo on `CAM_B/C` produces aligned depth.
- Two `DepthMerger` nodes attach depth to the object and palm detections separately.
- [utils/detection_merger.py](utils/detection_merger.py) combines those streams into one detection message with label offsets.
- Host nodes measure distances, render per-object distance output, and emit an alert stream.

## Constraints

- The current code hardcodes `DANGEROUS_OBJECTS = ["bottle", "cup"]`.
- The example requires three cameras and aligned stereo depth.
- Palm and object labels are merged into one namespace, so label offsets matter if you modify the model set.

## Related Examples

- [neural-networks/object-detection/social-distancing](https://github.com/luxonis/oak-examples/tree/main/neural-networks/object-detection/social-distancing): use this when you need person-to-person distance monitoring
- [neural-networks/object-detection/spatial-detections](https://github.com/luxonis/oak-examples/tree/main/neural-networks/object-detection/spatial-detections): use this when you need the general spatial detection baseline
- [neural-networks/object-tracking/collision-avoidance](https://github.com/luxonis/oak-examples/tree/main/neural-networks/object-tracking/collision-avoidance): use this when the safety signal should come from motion toward the camera

## Validation

- `Run:` `python3 main.py`
- `Success looks like:` the Visualizer shows the color stream, merged detections, distance annotations, and an alert output when palms get too close to dangerous objects
- `Common failure meaning:` stereo alignment is wrong, the device lacks the required camera topology, or the hardcoded dangerous-object classes are not present in the scene
