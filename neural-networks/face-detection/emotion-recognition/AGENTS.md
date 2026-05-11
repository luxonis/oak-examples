# AGENTS.md

## Summary

This is the repository reference for two-stage face emotion recognition. Use it when you need detected faces cropped into a second-stage classifier rather than a single-stage analytics model.

## Use This Example When

- You need per-face emotion classification.
- You want a reusable two-stage face pipeline with replay support.
- You need a lighter analytics example than gaze or fatigue detection.

## Do Not Use This Example When

- You only need face detection.
- You need age/gender, head pose, or landmarks instead of emotion labels.
- You need a custom frontend or richer app shell.

## Quick Facts

- `Category:` `neural-networks/face-detection/emotion-recognition`
- `Shape:` `script+standalone`
- `Primary task:` face detection plus emotion classification
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` RVC2 peripheral, RVC4 peripheral, and RVC4 standalone packaging
- `Requires:` YuNet detector and emotion-recognition model
- `Input:` camera frames by default or `ReplayVideo` via `--media_path`
- `Output:` `Video` and `Emotions`
- `Models:` YuNet and emotion-recognition YAMLs in [depthai_models/](depthai_models/)
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [utils/annotation_node.py](utils/annotation_node.py)
- [utils/arguments.py](utils/arguments.py)

## Architecture

- A first `ParsingNeuralNetwork` runs YuNet.
- `FrameCropper` generates per-face crops for the emotion model.
- A second `ParsingNeuralNetwork` performs emotion recognition.
- `GatherData` and [utils/annotation_node.py](utils/annotation_node.py) merge detections with the emotion predictions for display.

## Constraints

- Default FPS is intentionally conservative, especially on RVC2.
- Output quality depends on both first-stage face detections and second-stage classification.
- The example exposes only the combined emotion overlay, not separate face crops or raw per-face tensors.

## Related Examples

- [../age-gender](../age-gender/): use this when the second stage should predict age/gender instead
- [../head-posture-detection](../head-posture-detection/): use this when the second stage should predict head pose
- [../gaze-estimation](../gaze-estimation/): use this when you need the more complex multi-input gaze pipeline

## Validation

- `Run:` `python3 main.py`
- `Success looks like:` the Visualizer shows `Video` and `Emotions`, and detected faces receive emotion labels
- `Common failure meaning:` the detector misses faces, crop generation does not align with the source stream, or the replay path does not match the expected sizing
