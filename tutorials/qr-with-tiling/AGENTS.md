# AGENTS.md

## Summary

This is the repository reference for tiling-based QR detection with host-side decode. Use it when you need the repo’s clearest SAHI-style small-object detection tutorial.

## Use This Example When

- You need QR detection on small codes that benefit from tiling.
- You want a tiled detector followed by host-side decode.
- You need camera or replay input with adjustable grid size.

## Do Not Use This Example When

- You need a simple single-pass detector.
- You need pure OCR rather than QR detection plus decode.
- You need an RVC2-compatible tutorial.

## Quick Facts

- `Category:` `tutorials/qr-with-tiling`
- `Shape:` `script+standalone`
- `Primary task:` detect small QR codes by tiling the image and decode them on the host side
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` effectively RVC4/OAK4 only in current repo usage
- `Requires:` QRDet model assets, `pyzbar`/`zbar` for decoding labels, and host or packaged runtime support for `HostNode` processing
- `Input:` live camera by default or `ReplayVideo` via `--media_path`
- `Output:` `Video`, `Visualizations`, and `Tiling grid`
- `Models:` QRDet YAMLs in [depthai_models/](depthai_models/)
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [utils/host_qr_scanner.py](utils/host_qr_scanner.py)
- [utils/merge_img_detections.py](utils/merge_img_detections.py)
- [utils/arguments.py](utils/arguments.py)
- [oakapp.toml](oakapp.toml)

## Architecture

- [main.py](main.py) splits each frame into overlapping tiles with `Tiling`, crops them with `FrameCropper`, and runs QRDet on each tile.
- `CoordinatesMapper`, `GatherData`, and [utils/merge_img_detections.py](utils/merge_img_detections.py) merge tile detections back into image space.
- `ImgDetectionsFilter.useNms()` suppresses duplicate tile detections after merging.
- [utils/host_qr_scanner.py](utils/host_qr_scanner.py) optionally decodes each detected QR crop with `pyzbar` and emits both annotation output and grid visualization.

## Constraints

- The README explicitly treats this as OAK4-only due to missing RVC2 bindings, even though RVC2 YAMLs are present.
- If `pyzbar` is unavailable, detections still exist but decoded labels remain empty in [utils/host_qr_scanner.py](utils/host_qr_scanner.py).
- Tiling lowers throughput by design; this is the accuracy-for-speed tradeoff the tutorial is demonstrating.

## Related Examples

- [tutorials/full-fov-nn](https://github.com/luxonis/oak-examples/tree/main/tutorials/full-fov-nn): use this when you need resize/FOV tradeoffs instead of tiled inference
- [neural-networks/ocr/general-ocr](https://github.com/luxonis/oak-examples/tree/main/neural-networks/ocr/general-ocr): use this when you need general text OCR rather than QR detection
- [neural-networks/object-detection/yolo-host-decoding](https://github.com/luxonis/oak-examples/tree/main/neural-networks/object-detection/yolo-host-decoding): use this when you need host-side detection processing without the tiling/decode pattern

## Validation

- `Run:` `python3 main.py`
- `Larger grid:` `python3 main.py -r 3 -c 3`
- `Success looks like:` the Visualizer shows `Video`, `Visualizations`, and `Tiling grid`, and decoded QR labels appear when `pyzbar` is available
- `Common failure meaning:` the run is on unsupported hardware, `zbar`/`pyzbar` is missing, or the user expects high FPS despite tiled multi-pass inference
