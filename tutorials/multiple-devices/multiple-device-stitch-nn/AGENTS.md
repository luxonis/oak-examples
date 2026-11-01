# AGENTS.md

## Summary

Stitch overlapping RVC2 and RVC4 camera feeds into a panorama with native beta Stitching, then run tiled YOLO inference on the first selected device. Use it when you need the repo’s most elaborate multi-device visual-composition tutorial.

## Use This Example When

- You need a host-stitched multi-camera view.
- You want homography-based stitching plus object detection.
- You need a conceptual example for combining multiple devices into one wide scene.

## Do Not Use This Example When

- You need calibrated world-frame fusion instead of image stitching.
- You need a packaged or standalone deployment path.
- You need support for arbitrary camera ordering or moving cameras.

## Quick Facts

- `Category:` `tutorials/multiple-devices/multiple-device-stitch-nn`
- `Shape:` `multi-device-host`
- `Primary task:` stitch multiple device feeds and run tiled YOLO detections over the stitched image
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` none
- `Frontend:` none
- `Runs on:` host mode only, with at least two camera sources across RVC2, RVC4, or mixed devices
- `Requires:` overlapping textured FOV, static cameras, host CPU headroom, and DepthAI 3.11.0 with OpenCV support
- `Input:` live `CAM_A` by default; ordered device IDs/IPs and sockets are selectable
- `Output:` `Input-N`, full `Stitched`, resized `Inference`, `Patcher` and `PanoramaDetections` topics
- `Models:` YOLOv6 YAMLs in [depthai_models/](depthai_models/)
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md)
- [Device validation notes](docs/device.md)
- [main.py](main.py)
- [utils/merge_img_detections.py](utils/merge_img_detections.py)
- [utils/arguments.py](utils/arguments.py)

## Architecture

- [main.py](main.py) opens the selected first device as the default inference device and adds the remaining devices to the same pipeline. Camera nodes are explicitly assigned to devices.
- Native host `dai.beta.node.Stitching` owns synchronization, visual registration, cached composition, seams and virtual-camera metadata. `r` calls `resetTransform()`.
- Host ImageManip resizes the full BGR888i panorama into a fixed platform-appropriate BGR inference canvas while preserving transformation metadata.
- Tiling, FrameCropper, ParsingNeuralNetwork, GatherData, MergeImgDetections and NMS produce canvas detections. MergeImgDetections uses native transformTo against the timestamp-matched reference, both before NMS and when mapping back to the full panorama.
- Only autofocus-capable sensors receive focus controls; focus is disabled five seconds after startup/reset.

## Constraints

- Host-only; RVC2 and RVC4 sources can be mixed. The first selected device determines the inference platform/model.
- Static, overlapping, textured views are required for visual registration. Software Sync groups timestamps but does not align camera exposures.
- Explicit `--devices` is preferred in a shared office; `--sockets` applies to each device. Do not select busy devices or change their OS, credentials or persistent settings.
- There is deliberately no concatenation fallback. Failed registration leaves input topics available; no panorama/detections are fabricated. `--duration` fails when no panorama was produced.
- Use Perspective panorama projection: native transformTo rejects Equirectangular. CoordinatesMapper is intentionally avoided because depthai-nodes 0.7.0 rejects it on RVC2.
- RVC2 inference uses BGR888p; RVC4 uses BGR888i.
- Native output allocation is bounded by `--max-panorama-size`; ImageManip and NN crop sizes are independently bounded.
- Use `--no-nn` only for camera/stitch validation; it does not prove inference. Both dependency versions are pinned because Stitching is beta.

## Related Examples

- [tutorials/multiple-devices/multiple-devices-preview](https://github.com/luxonis/oak-examples/tree/main/tutorials/multiple-devices/multiple-devices-preview): use this when you need per-device outputs without stitching
- [tutorials/multiple-devices/spatial-detection-fusion](https://github.com/luxonis/oak-examples/tree/main/tutorials/multiple-devices/spatial-detection-fusion): use this when you need world-frame fused detections instead of a panorama image
- [tutorials/qr-with-tiling](https://github.com/luxonis/oak-examples/tree/main/tutorials/qr-with-tiling): use this when you need tiling as the main idea but not multi-device stitching

## Validation

- `Run:` `oakctl run-script python main.py --devices LEFT_ID RIGHT_ID`
- `Single-device sensors:` `python main.py --devices ID --sockets CAM_B CAM_C`
- `Bounded reset check:` append `--duration 60 --reset-after 25`; use `--no-nn` to isolate stitching
- `Evidence:` use `oakctl inspect frames Stitched` and inspect both inference and full panorama overlays
- `Recalculate:` focus the Visualizer and press `r`
- `Success looks like:` the Visualizer shows a stitched panorama with detection overlays, and pressing `r` recomputes alignment
- `Common failure meaning:` no panorama usually means insufficient overlap/texture or no synchronized groups; inspect source topics first
