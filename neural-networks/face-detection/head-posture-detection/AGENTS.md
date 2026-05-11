# AGENTS.md

## Summary

This is the repository reference for two-stage face detection plus head-pose estimation. Use it when you need yaw/pitch/roll from faces but do not need the full gaze pipeline.

## Use This Example When

- You need head-pose estimation from detected faces.
- You want a simpler second-stage face analytics pipeline than gaze estimation.
- You need camera or replay input with a packaged standalone path.

## Do Not Use This Example When

- You need age/gender, emotions, or gaze instead of head pose.
- You only need face detection.
- You need a landmark-heavy host-logic example.

## Quick Facts

- `Category:` `neural-networks/face-detection/head-posture-detection`
- `Shape:` `script+standalone`
- `Primary task:` face detection plus head-pose estimation
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` RVC2 peripheral, RVC4 peripheral, and RVC4 standalone packaging
- `Requires:` YuNet and head-pose-estimation models
- `Input:` camera frames by default or `ReplayVideo` via `--media_path`
- `Output:` `Video`, `Detections`, and `Pose`
- `Models:` YuNet and head-pose-estimation YAMLs in [depthai_models/](depthai_models/)
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [utils/annotation_node.py](utils/annotation_node.py)
- [utils/arguments.py](utils/arguments.py)

## Architecture

- YuNet runs as the first-stage face detector.
- `FrameCropper` generates pose-model inputs from detected face regions.
- A second `ParsingNeuralNetwork` predicts head pose on those crops.
- `GatherData` and [utils/annotation_node.py](utils/annotation_node.py) attach the pose output back to the face detections.

## Constraints

- This is still a crop-based two-stage pipeline, so first-stage face stability strongly affects the second stage.
- The current code publishes both raw detections and the pose overlay, unlike some other face analytics examples that only publish the final overlay.
- Replay sizing changes can upset the crop/projection assumptions.

## Related Examples

- [../gaze-estimation](../gaze-estimation/): use this when you need the larger face-plus-eyes-plus-head-pose pipeline
- [../age-gender](../age-gender/): use this when the second stage should do age/gender classification instead
- [../emotion-recognition](../emotion-recognition/): use this when the second stage should classify emotions instead

## Validation

- `Run:` `python3 main.py`
- `Success looks like:` the Visualizer shows `Video`, `Detections`, and `Pose`, and visible faces receive yaw/pitch/roll overlays
- `Common failure meaning:` face crops are misaligned, the detector is unstable, or the wrong platform model was selected
