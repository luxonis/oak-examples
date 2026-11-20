# AGENTS.md

## Summary

Calibrate OAK devices with the `MultiDeviceCalibration` node, run YOLO on each device, stitch a calibrated panorama with the `Stitching` node and merge all cameras' detections into it with `ImgDetectionsFilter`.

## Use This Example When

- You need one panorama from several devices with detections drawn once per object.
- You want the native multi-device chain: `MultiDeviceCalibration` -> `pipeline.setMultiDeviceCalibration` -> calibrated `Stitching` -> `ImgDetectionsFilter`.
- You need a reference for remapping and deduplicating detections across cameras.

## Do Not Use This Example When

- You need calibrated world-frame fusion or depth instead of a 2D panorama.
- You cannot keep the cameras fixed relative to each other after calibration.
- You need a packaged or standalone deployment path.

## Quick Facts

- `Category:` `tutorials/multiple-devices/multiple-device-stitch-nn`
- `Shape:` `multi-device-host`
- `Primary task:` calibrate devices, detect on each camera, stitch a calibrated panorama and merge the detections into it
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` none
- `Frontend:` none
- `Runs on:` host mode only, with at least two devices (RVC2, RVC4 or mixed)
- `Requires:` overlapping fields of view, a fixed rig, a textured scene during calibration, metric scale from a factory stereo pair on one device or `--known-distance`, factory intrinsics for the cameras used
- `Input:` live `CAM_A` of every selected device (first factory-calibrated camera when `CAM_A` is not calibrated, e.g. FFC boards); the calibration uses `CAM_B`/`CAM_C` where both are calibrated
- `Output:` `Stitched` and `PanoramaDetections` topics in the `Panorama` group; `Input-N` and `Detections-N` with `--show-inputs`
- `Models:` YOLOv6-nano YAMLs in [depthai_models/](depthai_models/)
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection` on port 8082

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [utils/arguments.py](utils/arguments.py)
- [Stitching documentation](https://docs.luxonis.com/software-v3/depthai/depthai-components/host_nodes/stitching)
- `docs/ImgDetectionsFilter.md` and `examples/python/MultiDevice/multi_device_detections_panorama.py` in depthai-core

## Architecture

- [main.py](main.py) runs two pipelines in sequence. `calibrate()` builds a `dai.beta.node.MultiDeviceCalibration` pipeline when `--calibration` does not exist or `--calibrate` is given: full-resolution `CAM_B`+`CAM_C` (devices with a calibrated stereo pair) or the panorama camera at 5 FPS per device, `setSampleCount`, optional `setKnownDistance` between the first cameras of the first two devices, `start` control, result saved with `result.getHandler().toJsonFile()`.
- `main()` loads the JSON with `dai.beta.MultiDeviceCalibrationHandler` and calls `pipeline.setMultiDeviceCalibration(handler.getGraph())` before creating nodes, so every camera transformation shares one origin.
- `calibrated_sockets()` keeps only connected cameras with factory intrinsics in the EEPROM; `panorama_socket()` picks `CAM_A` or, if it is not calibrated, the lowest calibrated socket. Both calibration and panorama use these, so the calibration graph always covers the stitched camera.
- Per device: `Camera(panorama_socket)` -> `DetectionNetwork` on that device with an undistorted `ImgFrameCapability` input and confidence threshold 0.5 (low-confidence boxes are dropped on the device, not sent to the host), plus one undistorted NV12 `requestOutput` view (640x400 times `--panorama-scale`) for the host.
- Host `Sync` (threshold one frame period) + `MessageDemux` route each device's detections to `ImgDetectionsFilter.inputs["camN"]`; the demux outputs declare `ImgDetections` as datatype. The filter uses `stitch.out` as `inputReference` and `stitch.outSourceMasks["inputN"]` as `inputSourceMasks["camN"]`, overlap mode NMS (or AVERAGE with `--average`), IoU threshold 0.4.
- Host `dai.node.Stitching` in `PANORAMA` mode with `setUseInputCalibration(True)`, projection from `--projection` (Cylindrical default), GRAPHCUT_COLOR seams unless `--no-blend`, max size 1600x800 times the scale.
- Visualizer topics `Stitched` and `PanoramaDetections` share the `Panorama` group; the viewer draws the newest detections over the newest frame, so no extra host synchronization is needed for display.
- Keys through `visualizer.waitKey`: `1`/`2`/`3` overlap OFF/NMS/AVERAGE, `W`/`S` IoU +/-0.05, `q` quit. Each change sends a complete `ImgDetectionsFilterConfig` on `inputConfig` and logs the new setting.

## Constraints

- Host-only; the networks run on the devices, everything else on the host. `createImplicitDevice=False`; devices are added explicitly from `--devices` and camera/network nodes are bound to them.
- Keep `pipeline.setMultiDeviceCalibration()` before `pipeline.start()`; calibration and panorama cannot share one pipeline because the calibration node is one-shot and host-only.
- Device order does not matter for the panorama; the calibration graph defines the geometry. All selected devices must appear in the calibration JSON, otherwise redo it with `--calibrate`.
- Detection inputs must stay synchronized upstream: the filter consumes one message per linked key and does not compare timestamps itself. Keep `--sync-threshold-ms` within one frame period.
- `ImgDetectionsFilter dropping rounds until a valid reference arrives` is logged once at startup until the first panorama; if it persists, the stitcher is not producing output (missing frames or a calibration that does not cover a device).
- Perspective projection needs a combined field of view below 180 degrees; Cylindrical and Equirectangular also handle wide rigs. Oversized panoramas are rejected, not resized.
- Parallax from nearby objects and partial objects at a camera edge remain; the filter merges boxes by overlap only, not by depth.
- Requirements use `depthai` from PyPI only (no snapshot index, no depthai-nodes). `MultiDeviceCalibration` and its handler are still under `dai.beta`.
- The generated `calibration.json` is git-ignored; do not commit rig-specific calibrations.
- One 1280x800 NV12 view (default `--panorama-scale 2`) at 10 FPS is about 120 Mbit/s per device: use gigabit Ethernet for network cameras. On a 100 Mbit link use `--panorama-scale 1` (about 30 Mbit/s) or lower `-fps`, otherwise frames arrive too late to sync and the panorama rate collapses (measured about 1.4 FPS at scale 2 versus 10 FPS at scale 1).

## Related Examples

- [tutorials/multiple-devices/multiple-devices-preview](https://github.com/luxonis/oak-examples/tree/main/tutorials/multiple-devices/multiple-devices-preview): use this when you need per-device outputs without stitching
- [tutorials/multiple-devices/spatial-detection-fusion](https://github.com/luxonis/oak-examples/tree/main/tutorials/multiple-devices/spatial-detection-fusion): use this when you need world-frame fused detections instead of a panorama image
- [tutorials/multiple-devices/multi-device-calibration](https://github.com/luxonis/oak-examples/tree/main/tutorials/multiple-devices/multi-device-calibration): use this when you only need the multi-device calibration file, for example for spatial fusion

## Validation

- `Calibrate and run:` `python3 main.py --devices DEVICE_1 DEVICE_2` (first run calibrates; `Calibration saved to ...` then `Pipeline started.`)
- `Reuse:` `python3 main.py --devices DEVICE_1 DEVICE_2 --show-inputs` reports `Using calibration ...` and skips the calibration pipeline
- `Success looks like:` the Visualizer shows one `Stitched` panorama with `PanoramaDetections` overlays, an object in the overlap has one box, and pressing `3` prints `Duplicates: AVERAGE`
- `Common failure meaning:` `has no factory calibration for its connected cameras` means the device EEPROM lacks intrinsics and cannot be used; `Calibration failed` means insufficient shared texture or missing scale (`--known-distance`); a persistent `dropping rounds` warning means no panorama is produced; misaligned seams mean the rig moved since calibration
