# AGENTS.md

## Summary

This is the repository reference for a multi-input, three-stage gaze estimation pipeline. Use it when you need the most complex face analytics wiring in the category rather than a simple two-stage crop pipeline.

## Use This Example When

- You need gaze estimation from face, eye, and head-pose inputs.
- You want a concrete example of multi-input model wiring.
- You need a face analytics baseline that goes beyond a single second-stage classifier.

## Do Not Use This Example When

- You only need face detection or a simple second-stage classifier.
- You need a generic multi-stage template without face-specific crop logic.
- You need the smallest possible replay/camera example.

## Quick Facts

- `Category:` `neural-networks/face-detection/gaze-estimation`
- `Shape:` `script+standalone`
- `Primary task:` face detection plus head-pose and gaze estimation
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` RVC2 peripheral, RVC4 peripheral, and RVC4 standalone packaging
- `Requires:` YuNet, head-pose-estimation, and gaze-estimation models
- `Input:` camera frames by default or `ReplayVideo` via `--media_path`
- `Output:` `Video` and `Gaze`
- `Models:` YuNet, head-pose-estimation, and gaze-estimation YAMLs in [depthai_models/](depthai_models/)
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [utils/process_keypoints.py](utils/process_keypoints.py)
- [utils/host_concatenate_head_pose.py](utils/host_concatenate_head_pose.py)
- [utils/annotation_node.py](utils/annotation_node.py)

## Architecture

- YuNet detects faces first.
- [utils/process_keypoints.py](utils/process_keypoints.py) converts detections into left-eye, right-eye, and face crop configs.
- A head-pose model runs on face crops, and [utils/host_concatenate_head_pose.py](utils/host_concatenate_head_pose.py) merges its yaw/pitch/roll outputs.
- A raw `NeuralNetwork` node consumes three inputs: left eye, right eye, and head-pose angles.
- `GatherData` and [utils/annotation_node.py](utils/annotation_node.py) merge the gaze output back into the displayed face overlay.

## Constraints

- This is a multi-input pipeline with several blocking/max-size settings; it is much easier to break than the simpler two-stage face examples.
- RVC4 uses a larger requested source resolution than RVC2 in [main.py](main.py).
- Replay or camera sizing changes can invalidate the crop logic if done blindly.

## Related Examples

- [neural-networks/face-detection/head-posture-detection](https://github.com/luxonis/oak-examples/tree/main/neural-networks/face-detection/head-posture-detection): use this when you need the simpler face-plus-head-pose pipeline
- [neural-networks/face-detection/fatigue-detection](https://github.com/luxonis/oak-examples/tree/main/neural-networks/face-detection/fatigue-detection): use this when you need landmarks and heuristics instead of gaze vectors
- [neural-networks/object-detection/yolo-world](https://github.com/luxonis/oak-examples/tree/main/neural-networks/object-detection/yolo-world): use this when you need another multi-input model reference

## Validation

- `Run:` `python3 main.py`
- `Success looks like:` the Visualizer shows `Video` and `Gaze`, and gaze overlays follow visible faces
- `Common failure meaning:` the eye/face crop logic drifted, the multi-input tensor wiring is out of sync, or the replay sizing is incompatible with the crop pipeline
