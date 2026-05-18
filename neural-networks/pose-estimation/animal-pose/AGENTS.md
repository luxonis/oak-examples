# AGENTS.md

## Summary

This is the repository reference for two-stage animal pose estimation. Use it when you need animal detection followed by pose landmarks rather than human or hand pose.

## Use This Example When

- You need animal pose estimation.
- You want a two-stage detect-then-pose example with non-human classes.
- You need camera or replay input with packaged standalone support.

## Do Not Use This Example When

- You need human pose or hand pose.
- You need generic object detection only.
- You need 3D animal geometry rather than 2D landmarks.

## Quick Facts

- `Category:` `neural-networks/pose-estimation/animal-pose`
- `Shape:` `script+standalone`
- `Primary task:` animal detection plus pose estimation
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` RVC2 peripheral, RVC4 peripheral, and RVC4 standalone packaging
- `Requires:` wildlife megadetector and superanimal landmarker models
- `Input:` camera frames by default or `ReplayVideo` via `--media_path`
- `Output:` `Video`, `Detections`, and `Pose`
- `Models:` wildlife and superanimal YAMLs in [depthai_models/](depthai_models/)
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [utils/annotation_node.py](utils/annotation_node.py)
- [utils/arguments.py](utils/arguments.py)

## Architecture

- The wildlife detector runs first.
- `ImgDetectionsFilter` keeps only `VALID_LABELS = [0]` in the current code path.
- `FrameCropper` extracts padded crops for the superanimal pose model.
- `GatherData` and [utils/annotation_node.py](utils/annotation_node.py) merge detections with pose landmarks and draw the skeleton.

## Constraints

- The current repo state filters to one label ID, so it is narrower than a generic wildlife detector.
- Input is forced to NV12 in replay mode.
- Pose quality depends on the first-stage detection boxes and the fixed padding factor.

## Related Examples

- [neural-networks/pose-estimation/human-pose](https://github.com/luxonis/oak-examples/tree/main/neural-networks/pose-estimation/human-pose): use this when you need human pose
- [neural-networks/pose-estimation/hand-pose](https://github.com/luxonis/oak-examples/tree/main/neural-networks/pose-estimation/hand-pose): use this when you need hand pose and gesture logic
- [neural-networks/3D-detection/objectron](https://github.com/luxonis/oak-examples/tree/main/neural-networks/3D-detection/objectron): use this when you need another detect-then-keypoint workflow with geometry flavor

## Validation

- `Run:` `python3 main.py`
- `Success looks like:` the Visualizer shows animal detections and pose skeletons on the same stream
- `Common failure meaning:` the wildlife detector is not finding the intended class, or the fixed label/padding assumptions do not match the chosen scene
