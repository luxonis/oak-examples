# AGENTS.md

## Summary

This is the repository reference for fusing spatial detections from multiple calibrated OAK devices into a single bird’s-eye view. Use it when you need shared-world multi-camera perception rather than per-device outputs.

## Use This Example When

- You need multi-device 3D detection fusion.
- You already have calibration outputs from [../multi-cam-calibration](../multi-cam-calibration/).
- You want the repo’s most direct Bird’s Eye View fusion example.

## Do Not Use This Example When

- You do not have extrinsic calibration files yet.
- You need image stitching instead of world-frame fusion.
- You need a standalone packaged deployment.

## Quick Facts

- `Category:` `tutorials/multiple-devices/spatial-detection-fusion`
- `Shape:` `multi-device-host`
- `Primary task:` fuse multi-camera spatial detections into a shared BEV visualization
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` none
- `Frontend:` none
- `Runs on:` host mode only, with one or more calibrated stereo-capable devices
- `Requires:` `calibration_data/extrinsics_<MXID>.npz` files, stereo-capable cameras, and host-side SciPy/OpenCV dependencies
- `Input:` live `CAM_A/B/C` per device
- `Output:` per-device passthrough/detections plus `BEV Canvas`, `BEV Cameras`, `BEV History Trails`, and `BEV Detections`
- `Models:` fixed model slug in [utils/config.py](utils/config.py)
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [utils/config.py](utils/config.py)
- [utils/fusion.py](utils/fusion.py)
- [utils/birds_eye_view.py](utils/birds_eye_view.py)
- [utils/utility.py](utils/utility.py)
- [utils/arguments.py](utils/arguments.py)

## Architecture

- [main.py](main.py) loads extrinsic calibrations, chooses the first valid device as the main pipeline host, and creates a `FusionManager` there.
- Each device runs a `SpatialDetectionNetwork` and forwards `SpatialImgDetections` into the fusion manager through a dedicated per-device input.
- [utils/fusion.py](utils/fusion.py) converts camera coordinates into world coordinates, groups near-simultaneous detections, and prunes duplicates per camera.
- [utils/birds_eye_view.py](utils/birds_eye_view.py) renders the fused results, camera poses, and history trails into BEV annotation topics.

## Constraints

- Only devices with matching extrinsic files in `calibration_data/` are used.
- This example depends on the multi-cam calibration workflow; moving cameras after calibration invalidates the fusion geometry.
- The first configured device becomes the main host for `FusionManager` and `BirdsEyeView`.
- `BEV_LABELS` in [utils/config.py](utils/config.py) is empty by default, which means all labels are shown.

## Related Examples

- [../multi-cam-calibration](../multi-cam-calibration/): run this first to create the required extrinsic files
- [../multiple-devices-preview](../multiple-devices-preview/): use this when you only need one independent pipeline per device
- [../../../neural-networks/object-detection/spatial-detections](../../../neural-networks/object-detection/spatial-detections/): use this when you need the single-device spatial-detection baseline

## Validation

- `Run:` `python3 main.py`
- `Success looks like:` the Visualizer shows per-device detection streams plus the BEV topics, and only calibrated devices participate
- `Common failure meaning:` extrinsic files are missing or stale, the devices are not stereo-capable, or the user expects a standalone or stitching-based solution instead of world-frame fusion
