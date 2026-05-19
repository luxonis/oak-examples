# AGENTS.md

## Summary

This is the repository reference for running YOLO on-device while decoding raw outputs on the host. Use it when you need control over the decode thresholds or want the host-decoding pattern rather than parser-managed detections.

## Use This Example When

- You need host-side YOLO decode logic.
- You want confidence and IoU thresholds controlled in the host decoder.
- You need camera or replay input with a packaged standalone path.

## Do Not Use This Example When

- You are fine with the standard parsed detection path.
- You need stereo spatial detections.
- You need a multi-model or multi-stage detector.

## Quick Facts

- `Category:` `neural-networks/object-detection/yolo-host-decoding`
- `Shape:` `script+standalone`
- `Primary task:` run YOLO and decode raw outputs on the host
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` RVC2 peripheral, RVC4 peripheral, and RVC4 standalone packaging
- `Requires:` YOLOv6 model, host decode logic, and optional replay input
- `Input:` camera frames by default or `ReplayVideo` via `--media_path`
- `Output:` `Camera` and `Detections`
- `Models:` YOLOv6 YAMLs in [depthai_models/](depthai_models/)
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [utils/host_decoding.py](utils/host_decoding.py)
- [utils/yolo_decode.py](utils/yolo_decode.py)
- [utils/arguments.py](utils/arguments.py)

## Architecture

- The camera or replay source is resized into the model input shape.
- A raw `dai.node.NeuralNetwork` runs YOLO without a parser.
- [utils/host_decoding.py](utils/host_decoding.py) decodes raw network outputs and exposes detections to the Visualizer.
- Decode thresholds come from `--confidence_thresh` and `--iou_thresh`.

## Constraints

- The requested input source is larger than the model input on purpose to preserve more source detail before resizing.
- This is a host-decode example, so it is less reusable than parser-backed examples when you do not need threshold/decode control.
- The decode logic is YOLO-specific; it is not a generic raw-output pattern for arbitrary models.

## Related Examples

- [neural-networks/object-detection/spatial-detections](https://github.com/luxonis/oak-examples/tree/main/neural-networks/object-detection/spatial-detections): use this when you want the standard parsed spatial detection baseline
- [neural-networks/object-detection/barcode-detection-conveyor-belt](https://github.com/luxonis/oak-examples/tree/main/neural-networks/object-detection/barcode-detection-conveyor-belt): use this when you want another detect-then-host-postprocess pattern
- [neural-networks/generic-example](https://github.com/luxonis/oak-examples/tree/main/neural-networks/generic-example): use this when you want the simplest parsed single-model detector scaffold

## Validation

- `Run:` `python3 main.py`
- `Success looks like:` the Visualizer shows `Camera` and `Detections`, and threshold changes alter which boxes survive host decoding
- `Common failure meaning:` the host decoder and model output no longer match, or the input resolution/resize path was changed without preserving the current assumptions
