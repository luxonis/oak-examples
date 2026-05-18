# AGENTS.md

## Summary

This is the repository reference for barcode-region detection followed by host-side barcode decoding. Use it when you need a conveyor-style detect-then-decode workflow rather than a pure detector.

## Use This Example When

- You need host-side barcode decoding after a neural detection stage.
- You want a conveyor-belt-oriented baseline with large source resolution.
- You need a packaged example that couples detection, crop creation, and decoding.

## Do Not Use This Example When

- You only need barcode region detections.
- You need QR or barcode detection without host decoding.
- You need a generic single-model object detector.

## Quick Facts

- `Category:` `neural-networks/object-detection/barcode-detection-conveyor-belt`
- `Shape:` `script+standalone`
- `Primary task:` detect barcode regions and decode them on the host
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` RVC2 peripheral, RVC4 peripheral, and RVC4 standalone packaging; most suited to OAK4-CS per the category overview
- `Requires:` barcode-detection model and high-resolution camera or matching replay input
- `Input:` camera frames by default or `ReplayVideo` via `--media_path`
- `Output:` `Barcode Overlay`
- `Models:` barcode-detection YAMLs in [depthai_models/](depthai_models/)
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [utils/barcode_decoder.py](utils/barcode_decoder.py)
- [utils/host_crop_config_creator.py](utils/host_crop_config_creator.py)
- [utils/simple_barcode_overlay.py](utils/simple_barcode_overlay.py)

## Architecture

- A neural barcode detector runs on the resized full frame.
- [utils/host_crop_config_creator.py](utils/host_crop_config_creator.py) turns detections into crop configs for candidate barcode regions.
- A second `ImageManip` path crops those regions from the original input.
- [utils/barcode_decoder.py](utils/barcode_decoder.py) performs host-side decoding on the cropped regions.
- [utils/simple_barcode_overlay.py](utils/simple_barcode_overlay.py) draws decode results back onto the displayed stream.

## Constraints

- The live camera path assumes a very large `2592x1944` source and manual exposure tuning in [main.py](main.py).
- Decode quality depends on both the first-stage detector and the crop/resize path.
- This is not a generic barcode scanner; it is optimized around a conveyor-style workflow.

## Related Examples

- [neural-networks/object-detection/yolo-host-decoding](https://github.com/luxonis/oak-examples/tree/main/neural-networks/object-detection/yolo-host-decoding): use this when you want another detect-then-host-postprocess pattern
- [apps/qr-tiling](https://github.com/luxonis/oak-examples/tree/main/apps/qr-tiling): use this when the task is QR-specific rather than conveyor-style barcode decoding
- [neural-networks/generic-example](https://github.com/luxonis/oak-examples/tree/main/neural-networks/generic-example): use this when you only need the detector stage

## Validation

- `Run:` `python3 main.py`
- `Success looks like:` the Visualizer shows `Barcode Overlay`, and detected barcodes receive decoded overlays
- `Common failure meaning:` the detector is not finding barcode regions, the source resolution is too low, or the host decoder is not receiving valid crops
