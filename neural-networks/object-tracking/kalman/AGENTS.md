# AGENTS.md

## Summary

This is the repository reference for Kalman-filtered spatial tracking. Use it when you need smoothed tracked boxes and spatial coordinates from stereo-backed detections.

## Use This Example When

- You need smoothing of tracked person detections.
- You want spatial detections fused with a host-side Kalman filter.
- You need a stereo tracking reference with calibration-aware depth geometry.

## Do Not Use This Example When

- You need embedding-based tracking.
- You need directional flow counting rather than smoothing.
- You need a generic 2D tracker without metric depth.

## Quick Facts

- `Category:` `neural-networks/object-tracking/kalman`
- `Shape:` `script+standalone`
- `Primary task:` smooth tracked person detections and spatial coordinates
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` devices with `CAM_A`, `CAM_B`, and `CAM_C`; RVC2 peripheral, RVC4 peripheral, and RVC4 standalone packaging
- `Requires:` metric depth, calibration, and person detections
- `Input:` live color plus stereo pair
- `Output:` `Video` and `Tracklets`
- `Models:` YOLOv6 YAMLs in [depthai_models/](depthai_models/)
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [utils/kalman_filter_node.py](utils/kalman_filter_node.py)
- [utils/kalman_filter.py](utils/kalman_filter.py)
- [utils/arguments.py](utils/arguments.py)

## Architecture

- A `SpatialDetectionNetwork` runs on `CAM_A` with metric depth from `Depth`.
- `ObjectTracker` produces person tracklets.
- `main.py` reads calibration to compute baseline and focal length.
- [utils/kalman_filter_node.py](utils/kalman_filter_node.py) uses that geometry plus tracklets to smooth the reported state.

## Constraints

- The current code tracks only the `person` label.
- The filter depends on calibration-derived baseline and focal length for its spatial smoothing path.
- This is a live-camera stereo example; there is no replay path in the current code.

## Related Examples

- [neural-networks/object-tracking/collision-avoidance](https://github.com/luxonis/oak-examples/tree/main/neural-networks/object-tracking/collision-avoidance): use this when you need motion-based alerts instead of smoothing
- [neural-networks/object-tracking/deepsort-tracking](https://github.com/luxonis/oak-examples/tree/main/neural-networks/object-tracking/deepsort-tracking): use this when you need embedding-based tracking
- [neural-networks/object-detection/spatial-detections](https://github.com/luxonis/oak-examples/tree/main/neural-networks/object-detection/spatial-detections): use this when you need the unsmoothed baseline spatial detections

## Validation

- `Run:` `python3 main.py`
- `Success looks like:` the Visualizer shows `Video` and `Tracklets`, with smoother spatial boxes and IDs over time
- `Common failure meaning:` stereo calibration is wrong, the device lacks the required camera set, or the person-only assumption does not match the scene
