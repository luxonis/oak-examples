# AGENTS.md

## Summary

This is the repository reference for people segmentation with background blur. Use it when you need a segmentation-based privacy or presentation effect rather than detections or OCR.

## Use This Example When

- You need background blur driven by a person segmentation mask.
- You want a single-model segmentation example with visible postprocessing.
- You need camera or replay input with packaged standalone support.

## Do Not Use This Example When

- You need object detections or instance boxes.
- You need stereo-aware segmentation with depth interaction.
- You need text or face blur instead of person/background separation.

## Quick Facts

- `Category:` `neural-networks/segmentation/blur-background`
- `Shape:` `script+standalone`
- `Primary task:` segment people and blur the background
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` RVC2 peripheral, RVC4 peripheral, and RVC4 standalone packaging
- `Requires:` person-segmentation model such as DeepLabV3+
- `Input:` camera frames by default or `ReplayVideo` via `--media_path`
- `Output:` `Background blur`
- `Models:` DeepLabV3+ YAMLs in [depthai_models/](depthai_models/)
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [utils/blur_detections.py](utils/blur_detections.py)
- [utils/arguments.py](utils/arguments.py)

## Architecture

- `ParsingNeuralNetwork` runs the segmentation model on camera or replay input.
- [utils/blur_detections.py](utils/blur_detections.py) consumes the segmentation output and passthrough frame and emits a composited blurred-background frame.
- The Visualizer publishes only the processed output stream.

## Constraints

- This is segmentation-based blur, not detection-box blur.
- Default FPS is intentionally low on RVC2 because the segmentation path is heavier than most detector examples.
- There is no raw mask topic in the current UI.

## Related Examples

- [../../object-detection/text-blur](../../object-detection/text-blur/): use this when you need text blur
- [../../face-detection/blur-faces](../../face-detection/blur-faces/): use this when you need face blur
- [../depth-crop](../depth-crop/): use this when the segmentation mask should interact with stereo depth

## Validation

- `Run:` `python3 main.py`
- `Success looks like:` the Visualizer shows `Background blur`, and foreground people remain in focus while the background is blurred
- `Common failure meaning:` the segmentation model is not isolating people correctly, or the operator expected a raw segmentation mask instead of the composited effect
