# AGENTS.md

## Summary

Show image detection filtering and duplicate merging on a calibrated stereo or multi-device panorama. Compare unfiltered and filtered detections through the DepthAI Visualizer.

## Use This Example When

- You need the native `ImgDetectionsFilter` node's label, confidence, area, count, or overlap controls.
- You want stereo or multi-device detections expressed in one image coordinate system.
- You want to compare OFF, NMS, and AVERAGE at runtime.

## Do Not Use This Example When

- You need depth-aware spatial fusion or reliable close-range parallax correction.
- You need standalone packaging.
- You need visual feature registration without calibrated camera transformations.

## Quick Facts

- `Category:` `tutorials/image-filter-detections`
- `Shape:` `script`
- `Entrypoint:` [main.py](main.py)
- `Runs on:` RVC2 or RVC4 in host mode
- `Requires:` calibrated CAM_B/CAM_C on one device, or at least two CAM_A devices and a MultiDeviceCalibration graph JSON
- `Dependencies:` [requirements.txt](requirements.txt), including the pinned DepthAI development build
- `Input:` two stereo camera views by default; one CAM_A view per device with `--devices`
- `Output:` source inference previews and before/after panorama detection overlays
- `Models:` configurable Model Zoo slug, default `luxonis/yolov6-nano:r2-coco-512x288`
- `Visualizer / UI:` `dai.RemoteConnection`, HTTP port 8082
- `Standalone path:` none

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [requirements.txt](requirements.txt)

## Architecture

- One pipeline owns all devices. Multi-device mode applies the calibration graph before camera creation; stereo mode uses factory calibration.
- Each camera runs a platform-specific DetectionNetwork with the same label vocabulary and a confidence floor of 0.1.
- Host Sync pairs detections by timestamp. MessageDemux declares concrete ImgDetections outputs before connecting each camera key to two filter nodes.
- Host Stitching composes undistorted NV12 views using calibration and supplies the reference transformation to both filters.
- Both filters use Stitching source masks by default. The baseline remaps source-visible boxes with overlap OFF; the second adds label, confidence, panorama-area, count, and overlap settings.
- Both filters publish overlays beside the same panorama. Source groups show the original inference frames and detections.
- Keyboard changes send fresh complete configs; keep all CLI filters in `configure_filter` when adding runtime controls.

## Constraints

- Install `depthai==3.10.0.dev0+3e3471137d99c00fc0ce18a3105f8b1854258845` from [requirements.txt](requirements.txt), which includes the Luxonis snapshot package index. Do not build core as part of this example.
- Remove any previous local core build entry from PYTHONPATH so it does not override the installed package.
- Multi-device calibration must be the graph JSON saved by core's MultiDeviceCalibration example, not per-device `.npz` files from this repo.
- Inputs must retain valid camera transformations in a common origin and identical class IDs. Keep undistortion and `setUseInputCalibration(True)` enabled.
- Sync matches timestamps without synchronizing exposure. Its threshold must not exceed one frame period.
- Mapping ignores depth and translation; close-range parallax and full 360-degree seam-crossing boxes are unsupported.
- Source masks are enabled for both panorama views; fully hidden boxes are removed even in OFF mode. `--no-source-masks` can expose parallax offsets when a hidden camera's detection wins over the visible camera's box.

## Related Examples

- [tutorials/display-detections](https://github.com/luxonis/oak-examples/tree/main/tutorials/display-detections): detection display-coordinate mapping
- [tutorials/multiple-devices/multiple-device-stitch-nn](https://github.com/luxonis/oak-examples/tree/main/tutorials/multiple-devices/multiple-device-stitch-nn): detect on a stitched image using tiled inference
- [tutorials/multiple-devices/spatial-detection-fusion](https://github.com/luxonis/oak-examples/tree/main/tutorials/multiple-devices/spatial-detection-fusion): depth-aware world-coordinate fusion

## Validation

- `CLI:` after installing the requirements, run `python3.12 main.py --help`; invalid device/calibration combinations should fail before connecting.
- `Stereo:` `python3.12 main.py --labels 0 --confidence 0.6`
- `Multi-device:` `python3.12 main.py --devices DEVICE_A DEVICE_B --calibration calibration.json`
- `Success looks like:` startup logs `Pipeline started.` and the Visualizer shows source previews plus before/after overlays. Change 1/2/3, W/S, and +/-; CLI label, area, and count limits must remain active.
- `Additional checks:` compare both panorama views near seams. Repeat with `--no-source-masks` to expose hidden-camera boxes and `--no-blend` to check direct composition. Hidden source boxes should be removed from both views with default masks.
- `Common failures:` wrong Python ABI or imported DepthAI package, missing stereo cameras, incorrect graph JSON, moved cameras, or mismatched label vocabularies.
