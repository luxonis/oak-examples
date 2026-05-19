# AGENTS.md

## Summary

This is the repo reference for stereo neural inference followed by host-side 3D triangulation. Use it when you need two camera streams, paired detections/keypoints, and approximate XYZ reconstruction from left/right image correspondences.

## Use This Example When

- You need a dual-camera neural inference example.
- You want host-side triangulation from left/right keypoints instead of a standard stereo-depth map.
- You need a YuNet-based face demo with combined overlay views.
- You want a packaged example that still uses the Visualizer rather than a custom frontend.

## Do Not Use This Example When

- You need a generic point-cloud or disparity pipeline.
- You need multi-object spatial tracking with robust association logic.
- You need ToF.
- You need a minimal single-camera face detector.

## Quick Facts

- `Category:` `depth-measurement/triangulation`
- `Shape:` `script+standalone`
- `Primary task:` run face detection on both stereo cameras and estimate 3D coordinates by triangulation
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [backend-run.sh](backend-run.sh) and [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` stereo-capable devices with `CAM_B` and `CAM_C`
- `Requires:` stereo mono pair, calibration, and the platform-specific YuNet model bundle
- `Input:` left and right mono camera streams plus platform-specific YuNet inference
- `Output:` left/right face views, per-side detection and keypoint overlays, combined overlay view, disparity line, and measurement text
- `Models:` `yunet.<platform>.yaml` in [depthai_models/](depthai_models/)
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md): high-level intent and usage
- [main.py](main.py): dual-camera pipeline, encoder setup, and published topics
- [utils/host_triangulation.py](utils/host_triangulation.py): host node that draws overlays and computes triangulated outputs
- [utils/stereo_inference.py](utils/stereo_inference.py): depth/disparity math used by the host node
- [utils/arguments.py](utils/arguments.py): CLI surface
- [backend-run.sh](backend-run.sh): backend command for packaged runs
- [oakapp.toml](oakapp.toml): standalone service packaging and model path

## Architecture

- `populate_pipeline()` builds a left or right camera branch on `CAM_B` or `CAM_C`.
- Each branch requests frames at the YuNet input size and runs `ParsingNeuralNetwork`.
- The custom [utils/host_triangulation.py](utils/host_triangulation.py) host node consumes:
  - left camera frames
  - right camera frames
  - left detections
  - right detections
- Separate `VideoEncoder` branches produce the left, right, and combined display streams for the Visualizer.
- The host node emits annotations for:
  - left bounding boxes
  - right bounding boxes
  - left keypoints
  - right keypoints
  - disparity lines
  - measurement text

## Data Flow

- `CAM_B -> YuNet -> left detections`
- `CAM_C -> YuNet -> right detections`
- `left/right frames + detections -> Triangulation host node -> overlays + combined frame`
- `encoded left/right/combined frames + annotations -> Visualizer topics`

## Modification Guide

- `Safe to change:` topic names, overlay wording, encoder settings, model thresholds in the parser path
- `Requires care:` left/right correspondence assumptions, camera resolution versus model resolution, and calibration-dependent spatial math
- `Likely to break if changed blindly:` the matching logic in [utils/host_triangulation.py](utils/host_triangulation.py) or the focal-length/baseline math in [utils/stereo_inference.py](utils/stereo_inference.py)

## Common Adaptations

- `To swap face detection for another keypoint-capable model:` replace the YuNet YAML/model and keep the same parsed-output contract
- `To reuse only the combined overlay view:` keep [utils/host_triangulation.py](utils/host_triangulation.py) and simplify the side-specific topics
- `To move back to depth-map-based spatial data:` use [depth-measurement/stereo-on-host](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/stereo-on-host) or [depth-measurement/3d-measurement/rgbd-pointcloud](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/3d-measurement/rgbd-pointcloud)
- `To make the packaged run path your baseline:` start with [oakapp.toml](oakapp.toml) and [backend-run.sh](backend-run.sh)

## Constraints

- This is a demo association strategy, not a robust multi-face matching system.
- [utils/host_triangulation.py](utils/host_triangulation.py) only triangulates the first detection pair when detections exist on both sides.
- [utils/stereo_inference.py](utils/stereo_inference.py) computes disparity from Euclidean pixel distance between keypoint locations, so treat the reported XYZ values as demo outputs rather than a precision spatial reference.
- The example assumes stereo cameras on `CAM_B` and `CAM_C`.

## Non-Obvious Repo Conventions

- Left/right display topics are encoded with `VideoEncoder`; they are not raw image topics.
- The combined frame is generated on the host with `cv2.addWeighted`.
- `Measurements Info` is annotation-only text derived from the first keypoint pair, not a structured data stream.
- [oakapp.toml](oakapp.toml) uses a `runsvdir` service-style entrypoint even though there is no custom frontend.

## Related Examples

- [depth-measurement/stereo-on-host](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/stereo-on-host): use this when you need host-side stereo disparity comparison instead of keypoint triangulation
- [depth-measurement/3d-measurement/rgbd-pointcloud](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/3d-measurement/rgbd-pointcloud): use this when you need RGBD point clouds instead of per-face triangulation
- [neural-networks/face-detection/blur-faces](https://github.com/luxonis/oak-examples/tree/main/neural-networks/face-detection/blur-faces): use this when you need a single-camera YuNet-based face reference
- [depth-measurement/calc-spatial-on-host](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/calc-spatial-on-host): use this when you need manual ROI spatial measurement instead of detection-driven triangulation

## Validation

- `Run:` `python3 main.py`
- `Standalone run:` `oakctl app run .`
- `Success looks like:` the Visualizer shows left, right, and combined views with face boxes, keypoints, disparity lines, and measurement text
- `Common failure meaning:` the stereo camera topology is missing, the YuNet model bundle is unavailable, or left/right detections are not pairing well enough for triangulation
