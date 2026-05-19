# AGENTS.md

## Summary

This is the repository reference for a two-stage OCR pipeline: text detection followed by text recognition. Use it when you need a general text-reading baseline rather than blur or plate-specific logic.

## Use This Example When

- You need text detection plus recognition.
- You want a reusable two-stage OCR pipeline with camera or replay input.
- You need a packaged example that already handles crop generation and text overlays.

## Do Not Use This Example When

- You only need text blur.
- You need license-plate-specific OCR.
- You need a single-model text detector with no recognition stage.

## Quick Facts

- `Category:` `neural-networks/ocr/general-ocr`
- `Shape:` `script+standalone`
- `Primary task:` general text detection and recognition
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [backend-run.sh](backend-run.sh) and [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` RVC2 peripheral, RVC4 peripheral, and RVC4 standalone packaging
- `Requires:` Paddle text-detection and text-recognition models
- `Input:` camera frames by default or `ReplayVideo` via `--media_path`
- `Output:` `Video` and `Text`
- `Models:` Paddle text-detection and text-recognition YAMLs in [depthai_models/](depthai_models/)
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [utils/host_process_detections.py](utils/host_process_detections.py)
- [utils/annotation_node.py](utils/annotation_node.py)
- [utils/arguments.py](utils/arguments.py)

## Architecture

- A text detector runs on the input stream first.
- [utils/host_process_detections.py](utils/host_process_detections.py) turns detections into recognition crop configs.
- `FrameCropper` extracts word/line crops for the OCR model.
- `GatherData` associates recognized text back to the original detections.
- [utils/annotation_node.py](utils/annotation_node.py) renders text overlays, and the video path is encoded before publication.

## Constraints

- `REQ_WIDTH = 1152` and `REQ_HEIGHT = 640` are chosen to preserve useful detail for the second stage.
- OCR throughput depends on the number of detected text regions because each region becomes a recognition crop.
- The current example publishes overlay text, not a structured export format.

## Related Examples

- [neural-networks/object-detection/text-blur](https://github.com/luxonis/oak-examples/tree/main/neural-networks/object-detection/text-blur): use this when you need privacy blur instead of recognition
- [neural-networks/ocr/license-plate-recognition](https://github.com/luxonis/oak-examples/tree/main/neural-networks/ocr/license-plate-recognition): use this when you need the license-plate-specific three-stage OCR pipeline
- [neural-networks/generic-example](https://github.com/luxonis/oak-examples/tree/main/neural-networks/generic-example): use this when you only need the text detector as a single-model baseline

## Validation

- `Run:` `python3 main.py`
- `Success looks like:` the Visualizer shows encoded `Video` plus `Text` annotations that follow visible text regions
- `Common failure meaning:` crops are not being generated correctly, the detector and recognizer are out of sync, or the scene resolution is too low for the OCR stage
