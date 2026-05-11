# AGENTS.md

## Summary

This is the repository reference for two-stage 3D bounding-box estimation with Objectron. Use it when you need detect-then-crop-then-estimate 3D keypoints rather than a plain 2D detector or stereo depth baseline.

## Use This Example When

- You need a two-stage pipeline that turns 2D detections into 3D pose/keypoint estimates.
- You want a host-visualized reference for Objectron-style geometry output.
- You need camera or replay input support with a packaged standalone path.

## Do Not Use This Example When

- You need generic 2D detection only.
- You need stereo depth or spatial coordinates from a stereo pair.
- You need the broader task family described in the README rather than the current chair-only implementation.

## Quick Facts

- `Category:` `neural-networks/3D-detection/objectron`
- `Shape:` `script+standalone`
- `Primary task:` 2-stage chair detection plus 3D Objectron pose/keypoint estimation
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` RVC2 peripheral, RVC4 peripheral, and RVC4 standalone packaging
- `Requires:` camera input or replay media, packaged detection and Objectron models
- `Input:` camera frames by default or `ReplayVideo` through `--media_path`
- `Output:` `Video` and `Position`
- `Models:` [depthai_models/objectron_chair.RVC2.yaml](depthai_models/objectron_chair.RVC2.yaml), [depthai_models/objectron_chair.RVC4.yaml](depthai_models/objectron_chair.RVC4.yaml), plus YOLOv6 detector YAMLs
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [utils/annotation_node.py](utils/annotation_node.py)
- [utils/arguments.py](utils/arguments.py)
- [oakapp.toml](oakapp.toml)

## Architecture

- A first-stage YOLOv6 detector runs on camera or replay input.
- `ImgDetectionsFilter` keeps only `VALID_LABELS = [56]`, which is the COCO `chair` label in the current code.
- `FrameCropper` extracts padded chair crops for the Objectron model.
- A second `ParsingNeuralNetwork` runs the `objectron_chair` model on those crops.
- `GatherData` re-associates second-stage outputs with first-stage detections, and [utils/annotation_node.py](utils/annotation_node.py) draws the 3D skeleton/pose overlay.

## Constraints

- Despite the README’s broader Objectron framing, the current repo state is chair-only.
- `PADDING = 0.2` is baked into both crop generation and annotation reprojection.
- Default FPS is intentionally low on RVC2 and lower than many detection examples because this is a two-stage geometry workflow.

## Related Examples

- [../../object-detection/spatial-detections](../../object-detection/spatial-detections/): use this when you need stereo spatial detections instead of model-based 3D boxes
- [../../generic-example](../../generic-example/): use this when you only need a single-model baseline
- [../../pose-estimation/animal-pose](../../pose-estimation/animal-pose/): use this when you need detect-then-crop-then-keypoints without 3D box fitting

## Validation

- `Run:` `python3 main.py`
- `Success looks like:` the Visualizer shows `Video` and `Position`, and detected chairs receive 3D keypoint/box overlays
- `Common failure meaning:` the detector is not finding chairs, the wrong platform model is being used, or replay media does not match the expected frame type
