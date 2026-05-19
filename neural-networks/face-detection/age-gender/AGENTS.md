# AGENTS.md

## Summary

This is the repository reference for two-stage face analytics with age and gender prediction. Use it when you need detect-then-crop face inference rather than a single-stage detector.

## Use This Example When

- You need age/gender prediction for detected faces.
- You want a baseline two-stage face pipeline with camera or replay input.
- You need a packaged example that already handles crop generation and output association.

## Do Not Use This Example When

- You only need face detection.
- You need landmarks, emotions, gaze, or head pose instead of age/gender.
- You need a custom frontend.

## Quick Facts

- `Category:` `neural-networks/face-detection/age-gender`
- `Shape:` `script+standalone`
- `Primary task:` face detection plus age/gender recognition
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [backend-run.sh](backend-run.sh) and [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` RVC2 peripheral, RVC4 peripheral, and RVC4 standalone packaging
- `Requires:` YuNet face detector and age/gender recognition models
- `Input:` camera frames by default or `ReplayVideo` via `--media_path`
- `Output:` `Video` and `AgeGender`
- `Models:` YuNet and age/gender YAMLs in [depthai_models/](depthai_models/)
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [utils/annotation_node.py](utils/annotation_node.py)
- [utils/arguments.py](utils/arguments.py)

## Architecture

- YuNet runs as the first-stage face detector.
- `FrameCropper` extracts face crops from the original frame using the detector output.
- A second `ParsingNeuralNetwork` runs age/gender recognition on those crops.
- `GatherData` re-associates second-stage outputs with detections and [utils/annotation_node.py](utils/annotation_node.py) draws the final overlay.

## Constraints

- [main.py](main.py) raises the detector confidence threshold to `0.9` for stability, which is stricter than many other face examples.
- This is a face crop pipeline, so output quality depends heavily on first-stage detector stability.
- The packaged standalone path exists, but the logic is still the same two-stage Visualizer-oriented flow.

## Related Examples

- [neural-networks/face-detection/emotion-recognition](https://github.com/luxonis/oak-examples/tree/main/neural-networks/face-detection/emotion-recognition): use this when the second stage should predict emotions instead
- [neural-networks/face-detection/head-posture-detection](https://github.com/luxonis/oak-examples/tree/main/neural-networks/face-detection/head-posture-detection): use this when the second stage should predict head pose
- [neural-networks/face-detection/blur-faces](https://github.com/luxonis/oak-examples/tree/main/neural-networks/face-detection/blur-faces): use this when you only need privacy-preserving face blur

## Validation

- `Run:` `python3 main.py`
- `Success looks like:` the Visualizer shows `Video` and `AgeGender`, and detected faces receive age/gender overlays
- `Common failure meaning:` face detections are too unstable, replay sizing does not match the expected crop logic, or the wrong platform model was selected
