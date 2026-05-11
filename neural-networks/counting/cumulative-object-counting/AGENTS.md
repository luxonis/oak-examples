# AGENTS.md

## Summary

This is the repository reference for line-crossing cumulative counting with tracked detections. Use it when you need directional counts from object motion across a configurable axis rather than a simple per-frame total.

## Use This Example When

- You need up/down or left/right cumulative counts.
- You want object tracking added on top of a detector.
- You need camera or replay input with axis and ROI controls.

## Do Not Use This Example When

- You only need the number of people or objects in the current frame.
- You need depth-only counting.
- You need density-map counting without trackers.

## Quick Facts

- `Category:` `neural-networks/counting/cumulative-object-counting`
- `Shape:` `script+standalone`
- `Primary task:` cumulative line-crossing counts with object tracking
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` RVC2 peripheral, RVC4 peripheral, and RVC4 standalone packaging
- `Requires:` object detector, tracker support, and optional media input
- `Input:` camera frames by default or `ReplayVideo` via `--media_path`
- `Output:` `Video` and `Count`
- `Models:` default YOLOv6 YAMLs in [depthai_models/](depthai_models/)
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [utils/annotation_node.py](utils/annotation_node.py)
- [utils/arguments.py](utils/arguments.py)

## Architecture

- A `ParsingNeuralNetwork` runs the detector on camera or replay input.
- `ObjectTracker` tracks detections across frames.
- [utils/annotation_node.py](utils/annotation_node.py) applies the configured `axis` and `roi_position` logic and emits the cumulative count overlay.
- The example keeps tracker settings platform-specific, using different tracker types on RVC2 and RVC4.

## Constraints

- Counts depend on tracker continuity; this is not a detection-only counter.
- The result quality depends heavily on axis placement and replay/camera framing.
- Default FPS is set in code and is higher than some other counting examples to keep tracker state usable.

## Related Examples

- [../people-counter](../people-counter/): use this when you need per-frame totals without line crossing
- [../depth-people-counting](../depth-people-counting/): use this when the counting signal should come from depth instead of RGB detections
- [../../object-tracking/people-tracker](../../object-tracking/people-tracker/): use this when you want person-specific directional flow tracking

## Validation

- `Run:` `python3 main.py`
- `Success looks like:` the Visualizer shows `Video` and `Count`, and counts update only when tracked objects cross the configured boundary
- `Common failure meaning:` the detector is unstable, the tracker is losing IDs, or the axis/ROI parameters are not appropriate for the scene
