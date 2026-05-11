# AGENTS.md

## Summary

This is the repository reference for mask/no-mask detection using a PPE detector subset. Use it when you need a simple single-stage face-mask example rather than a two-stage face analytics pipeline.

## Use This Example When

- You need mask/no-mask detections.
- You want a single-stage model with minimal postprocessing.
- You need camera or replay input and a packaged standalone path.

## Do Not Use This Example When

- You need face analytics from cropped faces.
- You need raw full-PPE labeling.
- You need blur or landmark-based logic.

## Quick Facts

- `Category:` `neural-networks/face-detection/face-mask-detection`
- `Shape:` `script+standalone`
- `Primary task:` mask/no-mask detection from a PPE detector
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` RVC2 peripheral, RVC4 peripheral, and RVC4 standalone packaging
- `Requires:` PPE detection model or compatible substitute
- `Input:` camera frames by default or `ReplayVideo` via `--media_path`
- `Output:` `Video` and `Detections`
- `Models:` PPE detection YAMLs in [depthai_models/](depthai_models/)
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [utils/arguments.py](utils/arguments.py)

## Architecture

- `ParsingNeuralNetwork` runs the PPE detector on camera or replay input.
- `ImgDetectionsFilter` keeps only the hardcoded PPE labels used for `mask` and `no_mask`.
- The Visualizer shows the passthrough video plus filtered detections.

## Constraints

- The current repo state uses `ppe_detection`, not a dedicated face-mask-only model.
- `LABEL_ENCODING` exists in [main.py](main.py), but the current pipeline only filters labels; it does not build a separate label-mapper node.
- This is a single-stage detection example, so it does not crop faces for further refinement.

## Related Examples

- [../blur-faces](../blur-faces/): use this when you need privacy blur instead of mask classification
- [../age-gender](../age-gender/): use this when you need two-stage face analytics
- [../../generic-example](../../generic-example/): use this when you want the most generic single-model detector scaffold

## Validation

- `Run:` `python3 main.py`
- `Success looks like:` the Visualizer shows `Video` and `Detections`, with only the mask-related PPE labels kept
- `Common failure meaning:` the selected model does not expose the expected PPE labels, or the scene quality is not good enough for the detector
