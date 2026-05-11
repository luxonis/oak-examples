# AGENTS.md

## Summary

This is the repository reference for text detection followed by selective blur. Use it when you need privacy-oriented blur over text regions rather than faces or person segmentation.

## Use This Example When

- You need text-region blur.
- You want a simple detection-plus-host-postprocess example.
- You need camera or replay input with a packaged standalone path.

## Do Not Use This Example When

- You need OCR instead of blur.
- You need face blur or background blur instead of text blur.
- You need a generic detector baseline.

## Quick Facts

- `Category:` `neural-networks/object-detection/text-blur`
- `Shape:` `script+standalone`
- `Primary task:` detect text and blur the detected text regions
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` RVC2 peripheral, RVC4 peripheral, and RVC4 standalone packaging
- `Requires:` Paddle text-detection model
- `Input:` camera frames by default or `ReplayVideo` via `--media_path`
- `Output:` `Video` and `Blur Text`
- `Models:` Paddle text-detection YAMLs in [depthai_models/](depthai_models/)
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [utils/blur_detections.py](utils/blur_detections.py)
- [utils/arguments.py](utils/arguments.py)

## Architecture

- `ParsingNeuralNetwork` runs the text detector on camera or replay input.
- [utils/blur_detections.py](utils/blur_detections.py) consumes text detections plus passthrough frames and emits a blurred output stream.
- The Visualizer shows both the raw video and the blurred result.

## Constraints

- This is region blur only; it does not recognize or decode the text.
- Blur quality depends on the quality of the detector polygons/boxes.
- The example does not expose a tuning surface for blur strength in the current code.

## Related Examples

- [../../ocr/general-ocr](../../ocr/general-ocr/): use this when you need text recognition instead of blur
- [../../segmentation/blur-background](../../segmentation/blur-background/): use this when you need segmentation-based blur
- [../../face-detection/blur-faces](../../face-detection/blur-faces/): use this when the blur target should be faces

## Validation

- `Run:` `python3 main.py`
- `Success looks like:` the Visualizer shows `Video` and `Blur Text`, and visible text regions are blurred in the processed output
- `Common failure meaning:` text detections are weak, the replay/camera source does not provide suitable resolution, or the operator expected OCR rather than privacy blur
