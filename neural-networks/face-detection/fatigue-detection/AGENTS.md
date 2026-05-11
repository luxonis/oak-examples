# AGENTS.md

## Summary

This is the repository reference for fatigue-style face state analysis using face detection plus landmarks. Use it when you need a two-stage face pipeline with host-side logic on top of landmarks.

## Use This Example When

- You need fatigue or drowsiness-style logic derived from facial landmarks.
- You want YuNet face detection followed by a face-landmarker stage.
- You need camera or replay input with the Visualizer.

## Do Not Use This Example When

- You only need raw landmarks.
- You need emotion, age/gender, or gaze instead of fatigue logic.
- You need the smallest possible face pipeline.

## Quick Facts

- `Category:` `neural-networks/face-detection/fatigue-detection`
- `Shape:` `script+standalone`
- `Primary task:` face detection plus landmark-based fatigue analysis
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` RVC2 peripheral, RVC4 peripheral, and RVC4 standalone packaging
- `Requires:` YuNet and MediaPipe face-landmarker models
- `Input:` camera frames by default or `ReplayVideo` via `--media_path`
- `Output:` `Video`, `Detections`, and `Fatique`
- `Models:` YuNet and face-landmarker YAMLs in [depthai_models/](depthai_models/)
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [utils/annotation_node.py](utils/annotation_node.py)
- [utils/face_landmarks.py](utils/face_landmarks.py)
- [utils/arguments.py](utils/arguments.py)

## Architecture

- YuNet detects faces in the first stage.
- `FrameCropper` creates face crops for the landmark model.
- `GatherData` aligns landmark outputs back to the face detections.
- [utils/annotation_node.py](utils/annotation_node.py) applies the fatigue logic and renders the state overlay.

## Constraints

- The output topic is currently spelled `Fatique` in [main.py](main.py).
- This is a host-logic example on top of landmarks; it is not just a generic face-landmark demo.
- The fatigue result depends on the specific heuristic implemented in [utils/annotation_node.py](utils/annotation_node.py) and [utils/face_landmarks.py](utils/face_landmarks.py).

## Related Examples

- [../gaze-estimation](../gaze-estimation/): use this when you need a more complex face-landmark-derived gaze pipeline
- [../emotion-recognition](../emotion-recognition/): use this when the second stage should classify emotions
- [../../pose-estimation/hand-pose](../../pose-estimation/hand-pose/): use this when you need another landmark-heavy multi-stage pattern

## Validation

- `Run:` `python3 main.py`
- `Success looks like:` the Visualizer shows `Video`, `Detections`, and `Fatique`, and face state overlays respond to visible faces
- `Common failure meaning:` face detections are unstable, the landmark stage is not aligning with crops, or the operator expects a raw-landmarks example instead of heuristic fatigue logic
