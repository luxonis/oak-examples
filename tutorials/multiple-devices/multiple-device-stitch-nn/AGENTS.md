# AGENTS.md

## Summary

Stitch overlapping RVC2 and RVC4 camera feeds into a panorama with native Stitching, then run tiled YOLO inference on the first selected device. Display the panorama and tiled detections through the DepthAI Visualizer.

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
- `Requires:` overlapping textured FOV, static cameras, host CPU headroom, and the pinned DepthAI 3.12 development snapshot with OpenCV support
- `Input:` live `CAM_A` by default; ordered device IDs/IPs and sockets are selectable
- `Output:` full `Stitched` and `PanoramaDetections` topics; optional `Input-N` streams with `--show-inputs`
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
- Native host `dai.node.Stitching` owns synchronization, visual registration, cached composition, seams and virtual-camera metadata. Explicit `setUseInputCalibration(False)` preserves image-content registration because this snapshot defaults to calibrated composition. `r` calls `resetTransform()`.
- Host ImageManip resizes the full BGR888i panorama into a fixed platform-appropriate BGR inference canvas while preserving transformation metadata.
- Tiling and FrameCropper feed a native `dai.node.DetectionNetwork` on the first device. GatherData and MergeImgDetections map its tile detections directly to the timestamp-matched full panorama, then host `depthai_nodes.node.ImgDetectionsFilter.useNms()` applies per-class NMS. No second gathering/remapping stage is needed.
- The Visualizer owns display. The main loop only processes pipeline tasks and handles r/q; camera focus stays at its default.
- Keep the resized inference canvas internal. Publish only `PanoramaDetections` in the `Panorama` group with `Stitched`; publishing canvas detections too draws duplicate labels and boxes.
- Only the stitched panorama with detection overlays is published by default. `--show-inputs` additionally registers each camera output as `Input-N` for registration troubleshooting.

## Constraints

- Host-only; RVC2 and RVC4 sources can be mixed. The first selected device determines the inference platform/model.
- Image-content PANORAMA registration does not require inter-camera calibration. Static, overlapping, textured views are required; wide baselines and nearby objects can cause parallax. Software Sync groups timestamps but does not align camera exposures.
- Explicit `--devices` is required; `--sockets` applies to each device. Do not select busy devices or change their OS, credentials or persistent settings.
- The primary example uses two physical devices with `--devices LEFT_ID RIGHT_ID --sockets CAM_A`, one source per device. Two sockets on each of two devices produce four sources; a two-socket run on one device only validates the single-device diagnostic path.
- There is deliberately no concatenation fallback. Failed registration emits no panorama/detections; input topics are available only when `--show-inputs` is supplied.
- Use Perspective panorama projection: native transformTo rejects Equirectangular. CoordinatesMapper is intentionally avoided because depthai-nodes 0.7.0 rejects it on RVC2.
- RVC2 inference uses BGR888p; RVC4 uses BGR888i.
- Perspective projection requires a combined field of view below 180°. The 4096x2048 panorama limit rejects oversized registrations rather than resizing them. ImageManip and NN crop sizes are independently bounded.
- Requirements pin `depthai==3.12.0.dev0+d4cb5b0f547f42ad39312c0dec48802b41028fa7` and `depthai-nodes==0.7.0`, and include the Luxonis snapshot index. Stitching parameters are constants in main.py, not diagnostic CLI options.
- Keep GatherData/MergeImgDetections and the depthai-nodes NMS filter: the snapshot's native `dai.node.ImgDetectionsFilter` suppresses duplicates only across separate input keys, so applying it to one merged tile stream would leave duplicates.
- Prefer wired host networking for network cameras. Check the actual route to each device; connecting Ethernet does not migrate an existing Wi-Fi connection. Slow transport or processing can create stale-frame queues. Restart after changing the route and lower FPS when measuring performance.

## Related Examples

- [tutorials/multiple-devices/multiple-devices-preview](https://github.com/luxonis/oak-examples/tree/main/tutorials/multiple-devices/multiple-devices-preview): use this when you need per-device outputs without stitching
- [tutorials/multiple-devices/spatial-detection-fusion](https://github.com/luxonis/oak-examples/tree/main/tutorials/multiple-devices/spatial-detection-fusion): use this when you need world-frame fused detections instead of a panorama image
- [tutorials/qr-with-tiling](https://github.com/luxonis/oak-examples/tree/main/tutorials/qr-with-tiling): use this when you need tiling as the main idea but not multi-device stitching

## Validation

- `Two-device run:` `oakctl run-script python main.py --devices LEFT_ID RIGHT_ID --sockets CAM_A`
- `Single-device diagnostic only:` `python main.py --devices ID --sockets CAM_B CAM_C`
- `Input diagnostics:` add `--show-inputs` to publish source views; the default UI should show only one stitched-image panel with its detection overlays.
- `Capture:` `oakctl inspect frames Stitched --count 2 --out evidence/panorama --timeout 30s` and `oakctl inspect dump PanoramaDetections --count 2 --timeout 30s`
- `Platforms:` validate the normal main.py on an available RVC2 and RVC4, sequentially. The generic repository runner skips this multi-device example; no per-example test harness is required.
- `Recalculate:` focus the Visualizer and press `r`
- `Success looks like:` the Visualizer shows a stitched panorama with detection overlays, and pressing `r` recomputes alignment
- `Performance:` measure frame/message timing as well as process liveness. A two-RVC4, one-CAM_A-per-device 360p run reached 10 FPS over Ethernet; do not generalize that measurement to other rigs.
- `Common failure meaning:` no panorama usually means insufficient overlap/texture or no synchronized groups; inspect source topics first
