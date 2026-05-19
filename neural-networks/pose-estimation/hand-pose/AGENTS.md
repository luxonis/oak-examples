# AGENTS.md

## Summary

This is the repository reference for hand pose plus gesture recognition. Use it when you need palm detection, hand landmarks, and gesture logic in one flow.

## Use This Example When

- You need hand landmarks and gesture labels.
- You want a two-stage palm-to-hand-landmarks pipeline.
- You need camera or replay input with packaged standalone support.

## Do Not Use This Example When

- You need face or human full-body landmarks.
- You only need palm detection.
- You need a minimal generic landmark demo.

## Quick Facts

- `Category:` `neural-networks/pose-estimation/hand-pose`
- `Shape:` `script+standalone`
- `Primary task:` palm detection plus hand landmark estimation and gesture recognition
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [backend-run.sh](backend-run.sh) and [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` RVC2 peripheral, RVC4 peripheral, and RVC4 standalone packaging
- `Requires:` MediaPipe palm-detection and hand-landmarker models
- `Input:` camera frames by default or `ReplayVideo` via `--media_path`
- `Output:` `Video`, `Detections`, and `Pose`
- `Models:` palm-detection and hand-landmarker YAMLs in [depthai_models/](depthai_models/)
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [utils/process.py](utils/process.py)
- [utils/gesture_recognition.py](utils/gesture_recognition.py)
- [utils/annotation_node.py](utils/annotation_node.py)

## Architecture

- Palm detection runs first on the full frame.
- [utils/process.py](utils/process.py) turns detections into crop configs for the hand landmark model.
- `FrameCropper` extracts hand crops, and a second `ParsingNeuralNetwork` predicts landmarks.
- `GatherData` and [utils/annotation_node.py](utils/annotation_node.py) merge landmarks back to the source stream, while the gesture logic derives labels from the keypoints.

## Constraints

- The README explicitly calls out that real-time use wants OAK4-class hardware.
- The example includes gesture recognition logic on top of landmarks; it is more than a raw hand-pose demo.
- The source stream is fixed to `768x768` in the current code path.

## Related Examples

- [neural-networks/pose-estimation/human-pose](https://github.com/luxonis/oak-examples/tree/main/neural-networks/pose-estimation/human-pose): use this when you need person pose instead of hands
- [neural-networks/pose-estimation/animal-pose](https://github.com/luxonis/oak-examples/tree/main/neural-networks/pose-estimation/animal-pose): use this when you need another detect-then-pose pattern
- [neural-networks/face-detection/fatigue-detection](https://github.com/luxonis/oak-examples/tree/main/neural-networks/face-detection/fatigue-detection): use this when you need another landmark-heavy two-stage flow

## Validation

- `Run:` `python3 main.py`
- `Success looks like:` the Visualizer shows hand detections and pose overlays, and gesture logic reacts to visible hands
- `Common failure meaning:` palm detection is unstable, crops are misaligned, or the run is too heavy for the target device/FPS
