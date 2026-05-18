# AGENTS.md

## Summary

This is the repository reference for three-stage ALPR: vehicle detection, license-plate detection, and OCR. Use it when you need the repo’s most specialized OCR pipeline rather than the general two-stage text reader.

## Use This Example When

- You need automatic license plate recognition.
- You want the repo’s three-stage detection/crop/OCR pattern.
- You need a specialized vehicle-and-plate workflow on RVC4.

## Do Not Use This Example When

- You need general scene OCR.
- You need a single-stage or two-stage detector.
- You need RVC2 support.

## Quick Facts

- `Category:` `neural-networks/ocr/license-plate-recognition`
- `Shape:` `script+standalone`
- `Primary task:` detect vehicles, detect plates, and OCR the plates
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` RVC4 only
- `Requires:` vehicle detector, license-plate detector, OCR model, and large source frames
- `Input:` camera frames by default or `ReplayVideo` via `--media_path`
- `Output:` `License Plates`
- `Models:` YOLOv6, license-plate-detection, and Paddle text-recognition YAMLs in [depthai_models/](depthai_models/)
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [utils/config_sender_script.py](utils/config_sender_script.py)
- [utils/license_plate_sender_script.py](utils/license_plate_sender_script.py)
- [utils/visualizer_node.py](utils/visualizer_node.py)

## Architecture

- A first-stage vehicle detector runs on a very large source frame.
- Script nodes generate crop configs for vehicles and then for license plates inside those vehicle crops.
- A second detector finds plates inside each vehicle crop.
- A third OCR stage reads the cropped plates.
- [utils/visualizer_node.py](utils/visualizer_node.py) fuses the stages back into the displayed plate overlay.

## Constraints

- [main.py](main.py) explicitly raises on non-RVC4 platforms.
- `REQ_WIDTH` and `REQ_HEIGHT` are set to doubled `1920x1080`, which makes this much heavier than most examples.
- The OCR parser ignores a long list of token indexes in code, so blindly swapping OCR models is risky.

## Related Examples

- [neural-networks/ocr/general-ocr](https://github.com/luxonis/oak-examples/tree/main/neural-networks/ocr/general-ocr): use this when you need general text detection and recognition
- [neural-networks/object-detection/barcode-detection-conveyor-belt](https://github.com/luxonis/oak-examples/tree/main/neural-networks/object-detection/barcode-detection-conveyor-belt): use this when the detect-then-decode target is barcodes instead of plates
- [neural-networks/face-detection/gaze-estimation](https://github.com/luxonis/oak-examples/tree/main/neural-networks/face-detection/gaze-estimation): use this when you want another complex multi-stage crop pipeline

## Validation

- `Run:` `python3 main.py`
- `Success looks like:` the Visualizer shows `License Plates` with detected vehicles, plates, and OCR text merged into one output
- `Common failure meaning:` the device is not RVC4, the scene resolution is too poor for the crop cascade, or one of the scripted crop stages is no longer aligned with the model outputs
