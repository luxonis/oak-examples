# AGENTS.md

## Summary

Stitch overlapping RVC2 and RVC4 camera feeds into a panorama with native beta Stitching, then run tiled YOLO inference on the first selected device. Display the panorama and tiled detections through the DepthAI Visualizer.

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
- `Output:` `Input-N`, full `Stitched` and `PanoramaDetections` topics
- `Models:` YOLOv6 YAMLs in [depthai_models/](depthai_models/)
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [utils/merge_img_detections.py](utils/merge_img_detections.py)
- [utils/arguments.py](utils/arguments.py)
- [Current native Stitching documentation](https://docs.luxonis.com/software-v3/depthai/depthai-components/host_nodes/stitching)

## Architecture

- [main.py](main.py) opens the selected first device as the default inference device and adds the remaining devices to the same pipeline. Camera nodes are explicitly assigned to devices.
- Native host `dai.beta.node.Stitching` owns synchronization, visual registration, cached composition, seams and virtual-camera metadata. `r` calls `resetTransform()`.
- Host ImageManip resizes the full BGR888i panorama into a fixed platform-appropriate BGR inference canvas while preserving transformation metadata.
- Tiling and FrameCropper feed a native `dai.node.DetectionNetwork` on the first device. GatherData and MergeImgDetections map its tile detections directly to the timestamp-matched full panorama, then native host `dai.beta.node.ImgDetectionsFilter` applies NMS. No second gathering/remapping stage is needed.
- The Visualizer owns display. The main loop only processes pipeline tasks and handles r/q; camera focus stays at its default.
- Keep the resized inference canvas internal. Publish only `PanoramaDetections` in the `Panorama` group with `Stitched`; publishing canvas detections too draws duplicate labels and boxes.

## Constraints

- Host-only; RVC2 and RVC4 sources can be mixed. The first selected device determines the inference platform/model.
- Image-content PANORAMA registration does not require inter-camera calibration. Static, overlapping, textured views are required; wide baselines and nearby objects can cause parallax. Software Sync groups timestamps but does not align camera exposures.
- Explicit `--devices` is required; `--sockets` applies to each device. Do not select busy devices or change their OS, credentials or persistent settings.
- There is deliberately no concatenation fallback. Failed registration leaves input topics available; no panorama/detections are fabricated.
- Use Perspective panorama projection: native transformTo rejects Equirectangular. CoordinatesMapper is intentionally avoided because depthai-nodes 0.7.0 rejects it on RVC2.
- RVC2 inference uses BGR888p; RVC4 uses BGR888i.
- Perspective projection requires a combined field of view below 180°. The 4096x2048 panorama limit rejects oversized registrations rather than resizing them. ImageManip and NN crop sizes are independently bounded.
- Both dependency versions are pinned because Stitching is beta. Stitching parameters are constants in main.py, not diagnostic CLI options.
- The pinned release's native filter has one input and performs NMS after tile remapping. Keep GatherData/MergeImgDetections: the newer develop filter has a different multi-input API and suppresses duplicates only across separate input keys, so it cannot replace this chain directly.

## Related Examples

- [tutorials/multiple-devices/multiple-devices-preview](https://github.com/luxonis/oak-examples/tree/main/tutorials/multiple-devices/multiple-devices-preview): use this when you need per-device outputs without stitching
- [tutorials/multiple-devices/spatial-detection-fusion](https://github.com/luxonis/oak-examples/tree/main/tutorials/multiple-devices/spatial-detection-fusion): use this when you need world-frame fused detections instead of a panorama image
- [tutorials/qr-with-tiling](https://github.com/luxonis/oak-examples/tree/main/tutorials/qr-with-tiling): use this when you need tiling as the main idea but not multi-device stitching

## Validation

- `Run:` `oakctl run-script python main.py --devices LEFT_ID RIGHT_ID`
- `Single-device sensors:` `python main.py --devices ID --sockets CAM_B CAM_C`
- `Capture:` `oakctl inspect frames Stitched --count 2 --out evidence/panorama --timeout 30s` and `oakctl inspect dump PanoramaDetections --count 2 --timeout 30s`
- `Platforms:` validate the normal main.py on an available RVC2 and RVC4, sequentially. The generic repository runner skips this multi-device example; no per-example test harness is required.
- `Recalculate:` focus the Visualizer and press `r`
- `Success looks like:` the Visualizer shows a stitched panorama with detection overlays, and pressing `r` recomputes alignment
- `Common failure meaning:` no panorama usually means insufficient overlap/texture or no synchronized groups; inspect source topics first
