# AGENTS.md

## Summary

This is the repository’s standard reference for real-time object detections with spatial coordinates. Use it when you need the baseline stereo-aware object detection example before moving to a more specialized safety, tracking, or measurement workflow.

## Use This Example When

- You need the baseline spatial-detection pattern.
- You want RGB detections plus depth visualization in one packaged example.
- You need a reusable starting point for stereo-aligned object detection.

## Do Not Use This Example When

- You need custom host-side logic beyond annotations.
- You need person-only distance monitoring or safety-specific postprocessing.
- You need host-side YOLO decoding instead of parsed detections.

## Quick Facts

- `Category:` `neural-networks/object-detection/spatial-detections`
- `Shape:` `script+standalone`
- `Primary task:` object detection with stereo spatial coordinates
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [backend-run.sh](backend-run.sh) and [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` devices with `CAM_A`, `CAM_B`, and `CAM_C`; RVC2 peripheral, RVC4 peripheral, and RVC4 standalone packaging
- `Requires:` metric depth, calibration, and a compatible detection model
- `Input:` live color plus stereo pair
- `Output:` `Camera`, `Detections`, and `Depth`
- `Models:` default YOLOv6 YAMLs in [depthai_models/](depthai_models/)
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [utils/annotation_node.py](utils/annotation_node.py)
- [utils/arguments.py](utils/arguments.py)
- [oakapp.toml](oakapp.toml)

## Architecture

- `CAM_A` feeds a `SpatialDetectionNetwork`.
- `Depth` owns depth-source selection and is aligned to the color stream inside `SpatialDetectionNetwork`.
- [utils/annotation_node.py](utils/annotation_node.py) renders spatial coordinates from `nn.out`.
- Both RGB and depth streams are encoded before being published to the Visualizer.

## Constraints

- The example requires three cameras and aligned metric depth.
- RVC2 has a special `numShaves` path and output-size adjustment in [main.py](main.py).
- This is the baseline reference, so avoid adding specialized task logic here when a closer example already exists.

## Related Examples

- [neural-networks/object-detection/social-distancing](https://github.com/luxonis/oak-examples/tree/main/neural-networks/object-detection/social-distancing): use this when you need person-to-person distance monitoring
- [neural-networks/object-detection/human-machine-safety](https://github.com/luxonis/oak-examples/tree/main/neural-networks/object-detection/human-machine-safety): use this when you need palm/object safety logic
- [depth-measurement/3d-measurement/rgbd-pointcloud](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/3d-measurement/rgbd-pointcloud): use this when you need a point-cloud baseline instead of spatial boxes

## Validation

- `Run:` `python3 main.py`
- `Success looks like:` the Visualizer shows `Camera`, `Detections`, and `Depth`, with spatial coordinates attached to the detections
- `Common failure meaning:` stereo cameras are unavailable, alignment is wrong, or the selected detector does not fit the spatial-detection path
