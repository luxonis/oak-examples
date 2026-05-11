# AGENTS.md

## Summary

This is the repository reference for person detection plus human pose estimation with Lite-HRNet. Use it when you need body keypoints on detected people rather than a generic detector.

## Use This Example When

- You need human pose estimation.
- You want a person-detection first stage with a swappable pose model.
- You need camera or replay input with packaged standalone support.

## Do Not Use This Example When

- You need hand or animal pose instead of human pose.
- You need a single-stage detector.
- You need multi-person tracking rather than per-frame pose overlays.

## Quick Facts

- `Category:` `neural-networks/pose-estimation/human-pose`
- `Shape:` `script+standalone`
- `Primary task:` person detection plus human pose estimation
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` RVC2 peripheral, RVC4 peripheral, and RVC4 standalone packaging
- `Requires:` person detector and Lite-HRNet-style pose model
- `Input:` camera frames by default or `ReplayVideo` via `--media_path`
- `Output:` `Video`, `Detections`, and `Pose`
- `Models:` YOLOv6 and Lite-HRNet YAMLs in [depthai_models/](depthai_models/)
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [utils/annotation_node.py](utils/annotation_node.py)
- [utils/arguments.py](utils/arguments.py)

## Architecture

- A person detector runs first.
- `ImgDetectionsFilter` identifies the `person` class for the pose workflow.
- `FrameCropper` extracts padded person crops for Lite-HRNet.
- `GatherData` and [utils/annotation_node.py](utils/annotation_node.py) merge the keypoints and skeleton back to the original detections.

## Constraints

- The current code path is person-specific, even though the detector could emit other classes.
- The pose parser threshold is intentionally set to `0.0` so the overlay node can do the filtering instead.
- Replay sizing and crop padding affect downstream pose quality.

## Related Examples

- [../hand-pose](../hand-pose/): use this when you need hand landmarks and gesture logic
- [../animal-pose](../animal-pose/): use this when you need animal pose
- [../../reidentification/human-reidentification](../../reidentification/human-reidentification/): use this when you need to identify tracked people or faces rather than estimate pose

## Validation

- `Run:` `python3 main.py`
- `Success looks like:` the Visualizer shows `Video`, `Detections`, and `Pose`, and visible people receive skeleton overlays
- `Common failure meaning:` the detector is not stably finding people, crop generation drifted, or the selected pose model does not match the parser assumptions
