# AGENTS.md

## Summary

This is the repository reference for real-time face blurring. Use it when you need the smallest privacy-oriented face example in the repo.

## Use This Example When

- You need live face blurring.
- You want a minimal face-detection-plus-postprocess example.
- You need camera or replay input without a second-stage model.

## Do Not Use This Example When

- You need raw detections or analytics outputs.
- You need age, emotion, landmarks, or gaze.
- You need class-specific blur beyond face boxes.

## Quick Facts

- `Category:` `neural-networks/face-detection/blur-faces`
- `Shape:` `script+standalone`
- `Primary task:` detect faces and blur the detected regions
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` RVC2 peripheral, RVC4 peripheral, and RVC4 standalone packaging
- `Requires:` YuNet face detector
- `Input:` camera frames by default or `ReplayVideo` via `--media_path`
- `Output:` `FaceBlur`
- `Models:` YuNet YAMLs in [depthai_models/](depthai_models/)
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [utils/blur_detections.py](utils/blur_detections.py)
- [utils/arguments.py](utils/arguments.py)

## Architecture

- YuNet runs on camera or replay input through `ParsingNeuralNetwork`.
- [utils/blur_detections.py](utils/blur_detections.py) receives detections and passthrough frames and emits a blurred output frame.
- The Visualizer only receives the postprocessed `FaceBlur` stream.

## Constraints

- There is no separate detection topic in the current UI; the example is focused on the blurred output.
- Blur quality and privacy depend entirely on detector stability.
- This is a box-based blur, not a segmentation-based face mask.

## Related Examples

- [../face-mask-detection](../face-mask-detection/): use this when you need mask/no-mask classification instead of blur
- [../fatigue-detection](../fatigue-detection/): use this when you need face landmarks and state logic instead of privacy blur
- [../../object-detection/text-blur](../../object-detection/text-blur/): use this when the blur target should be text instead of faces

## Validation

- `Run:` `python3 main.py`
- `Success looks like:` the Visualizer shows `FaceBlur`, and visible faces are blurred in the output stream
- `Common failure meaning:` the face detector is not finding faces, or replay/camera input does not match the expected frame type
