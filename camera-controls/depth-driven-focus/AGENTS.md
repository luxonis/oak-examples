# AGENTS.md

## Summary

This is the best reference in the repo for autofocus driven by metric face distance. Use it when you need to detect faces, merge detections with depth, and convert that distance into lens-position updates automatically.

## Use This Example When

- You need to focus on detected faces instead of using manual focus.
- You want a reference for combining a face detector with unified metric depth.
- You need a host node that converts 3D distance into `CameraControl.setManualFocus(...)`.
- You want a camera-controls example that still runs in peripheral mode and has an RVC4 standalone path.

## Do Not Use This Example When

- You only need manual camera control with keyboard input.
- You need crop control or zooming rather than lens-position control.
- You do not have a stereo pair or an autofocus color camera.
- You need a generic face-detection example without depth-based actuation.

## Quick Facts

- `Category:` `camera-controls/depth-driven-focus`
- `Shape:` `script+standalone`
- `Primary task:` automatic face focus from metric depth
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` stereo-capable RVC2 peripheral, RVC4 peripheral, and RVC4 standalone packaging
- `Requires:` autofocus color camera on `CAM_A`, stereo mono cameras on `CAM_B` and `CAM_C`, and calibration
- `Input:` RGB frames for face detection and metric depth for face distance
- `Output:` `Video`, `Visualizations`, `Depth`, and `Focus distance`
- `Models:` platform-specific YuNet descriptors in [depthai_models/](depthai_models/)
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [main.py](main.py): full camera, depth, face-detection, and focus-control pipeline
- [utils/depth_driven_focus.py](utils/depth_driven_focus.py): face-distance-to-lens-position logic and overlay output
- [utils/arguments.py](utils/arguments.py): CLI surface
- [depthai_models/yunet.RVC2.yaml](depthai_models/yunet.RVC2.yaml): RVC2 model descriptor
- [depthai_models/yunet.RVC4.yaml](depthai_models/yunet.RVC4.yaml): RVC4 model descriptor
- [oakapp.toml](oakapp.toml): standalone packaging path

## Architecture

- `CAM_A` provides RGB frames for face detection.
- `Depth` owns depth-source selection and stereo camera setup when stereo is selected.
- A `ParsingNeuralNetwork` runs YuNet face detection.
- `DepthMerger` from `depthai_nodes` enriches face detections with metric depth.
- The custom [utils/depth_driven_focus.py](utils/depth_driven_focus.py) host node finds the closest detected face, converts the 3D distance to a lens position, and sends manual-focus commands back into the camera control queue.
- The host node also publishes annotation text showing the current face distance and current lens position.

## Data Flow

- `CAM_A -> YuNet face detector -> Visualizations`
- `Depth -> metric depth`
- `face detections + metric depth -> DepthMerger -> spatial face detections`
- `spatial face detections -> DepthDrivenFocus host node -> camera inputControl queue + Focus distance`

## Modification Guide

- `Safe to change:` default FPS, annotation text, lens-position curve, topic names, depth visualization settings
- `Requires care:` fixed camera sockets, depth alignment, focus-capable hardware assumptions, the polynomial mapping in `get_lens_position(...)`
- `Likely to break if changed blindly:` the focus-distance calculation, the calibration-dependent depth merge, or camera-control updates on devices without autofocus support

## Common Adaptations

- `To tune the focus curve:` edit `get_lens_position(...)` in [utils/depth_driven_focus.py](utils/depth_driven_focus.py)
- `To change the detector:` swap the YuNet YAML under [depthai_models/](depthai_models/) and keep the same depth-merging shape
- `To reuse only the focus-control host node:` keep [utils/depth_driven_focus.py](utils/depth_driven_focus.py) and feed it another `SpatialImgDetections` stream
- `To compare against manual control:` see [camera-controls/manual-camera-control](https://github.com/luxonis/oak-examples/tree/main/camera-controls/manual-camera-control)

## Constraints

- The example needs a stereo pair and an autofocus RGB camera.
- Camera sockets are fixed to `CAM_A`, `CAM_B`, and `CAM_C`.
- `Depth` uses `AUTO` backend selection; keep `Depth.setAlignTo(...)` aligned with the face-detection stream when changing the camera path.
- `DepthDrivenFocus` ignores lens position `255`, so that edge case is intentionally not sent to the camera.

## Non-Obvious Repo Conventions

- The focus host node computes Euclidean distance from `x`, `y`, and `z`, not just the forward `z` coordinate.
- The focus-control topic is an annotation output, not a direct numeric stream.
- RVC2 uses a special `setNNArchive(..., numShaves=7)` path, so the detector setup is platform-sensitive.
- `DepthMerger` comes from `depthai_nodes`, not from a local utility file in this example directory.

## Related Examples

- [camera-controls/manual-camera-control](https://github.com/luxonis/oak-examples/tree/main/camera-controls/manual-camera-control): use this when you want direct keyboard focus control
- [camera-controls/lossless-zooming](https://github.com/luxonis/oak-examples/tree/main/camera-controls/lossless-zooming): use this when you want crop/zoom to follow a face instead of moving the lens
- [neural-networks/face-detection/blur-faces](https://github.com/luxonis/oak-examples/tree/main/neural-networks/face-detection/blur-faces): use this when the face-detection part matters more than camera actuation

## Validation

- `Run:` `python3 main.py`
- `Standalone run:` `oakctl app run .`
- `Success looks like:` the Visualizer shows `Video`, `Visualizations`, `Depth`, and `Focus distance`, and the reported lens position changes as face distance changes
- `Common failure meaning:` the device lacks autofocus or stereo hardware, calibration is unavailable, or the face detector is not producing usable detections
