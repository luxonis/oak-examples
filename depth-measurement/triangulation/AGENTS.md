# AGENTS.md

## Summary

This is the repo reference for stereo neural inference followed by host-side 3D triangulation. Use it when you need two camera streams, paired detections/keypoints, and calibrated XYZ reconstruction from left/right image correspondences.

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
- `Standalone path:` [oakapp.toml](oakapp.toml)
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
- [oakapp.toml](oakapp.toml): standalone service packaging and model path

## Architecture

- `populate_pipeline()` builds a left or right camera branch on `CAM_B` or `CAM_C`.
- `StereoDepth` supplies distortion-corrected rectified images at YuNet input size, using calibrated translation. A host `RectifiedColor` node replicates mono into the model color format; each branch runs `ParsingNeuralNetwork` on that geometry.
- The host consumes inference passthrough frames and parsed detections, checks per-camera sequence identity and cross-camera timestamps within 5 ms, and uses rectified-left frame intrinsics.
- The custom [utils/host_triangulation.py](utils/host_triangulation.py) host node consumes:
  - left camera frames
  - right camera frames
  - left detections
  - right detections
- Raw left, right, and combined frames go to the Visualizer, supporting both platforms without an encoder-dependent format path.
- The host node emits annotations for:
  - left bounding boxes
  - right bounding boxes
  - left keypoints
  - right keypoints
  - disparity lines
  - measurement text

## Data Flow

- `CAM_B/CAM_C -> StereoDepth rectification -> YuNet -> left/right detections`
- `left/right frames + detections -> Triangulation host node -> overlays + combined frame`
- `raw left/right/combined frames + annotations -> Visualizer topics`

## Modification Guide

- `Safe to change:` topic names, overlay wording, encoder settings, model thresholds in the parser path
- `Requires care:` left/right correspondence assumptions, camera resolution versus model resolution, and calibration-dependent spatial math
- `Likely to break if changed blindly:` the matching logic in [utils/host_triangulation.py](utils/host_triangulation.py) or the focal-length/baseline math in [utils/stereo_inference.py](utils/stereo_inference.py)

## Common Adaptations

- `To swap face detection for another keypoint-capable model:` replace the YuNet YAML/model and keep the same parsed-output contract
- `To reuse only the combined overlay view:` keep [utils/host_triangulation.py](utils/host_triangulation.py) and simplify the side-specific topics
- `To move back to depth-map-based spatial data:` use [depth-measurement/stereo-on-host](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/stereo-on-host) or [depth-measurement/measurement-3d/rgbd-pointcloud](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/measurement-3d/rgbd-pointcloud)
- `To make the packaged run path your baseline:` start with [oakapp.toml](oakapp.toml) and [main.py](main.py)

## Constraints

- RVC2 YuNet explicitly uses 6-SHAVE superblob variants and one inference thread so the stereo rectification branch fits the resource budget.

- `RectifiedColor` runs on the host because RVC4 `ImageManip` cannot convert StereoDepth RAW8 to the model color format. This adds a host round trip, while retaining geometry and metadata.

- This is a demo association strategy, not a robust multi-face matching system.
- Only one face on each side is accepted; multiple faces suppress measurements. This does not guarantee identity association, so use a single-face scene.
- [utils/stereo_inference.py](utils/stereo_inference.py) uses signed horizontal disparity, calibrated baseline in mm and rectified-left intrinsics. It rejects disparity <= 0.5 px, non-finite points and vertical errors > 3 px. XYZ is in mm in the rectified-left camera frame: X right, Y down, Z forward.
- It assumes a horizontal stereo pair and corresponding YuNet keypoint indices. Rectification cannot fix incorrect detection association.
- The example assumes stereo cameras on `CAM_B` and `CAM_C`.

## Non-Obvious Repo Conventions

- Left/right display topics use the neural network passthrough frames to preserve the inference geometry.
- The combined frame is generated on the host with `cv2.addWeighted`.
- `Measurements Info` is annotation-only text derived from the first keypoint pair, not a structured data stream.
- [oakapp.toml](oakapp.toml) uses a `runsvdir` service-style entrypoint even though there is no custom frontend.

## Related Examples

- [depth-measurement/stereo-on-host](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/stereo-on-host): use this when you need host-side stereo disparity comparison instead of keypoint triangulation
- [depth-measurement/measurement-3d/rgbd-pointcloud](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/measurement-3d/rgbd-pointcloud): use this when you need RGBD point clouds instead of per-face triangulation
- [neural-networks/face-detection/blur-faces](https://github.com/luxonis/oak-examples/tree/main/neural-networks/face-detection/blur-faces): use this when you need a single-camera YuNet-based face reference
- [depth-measurement/calc-spatial-on-host](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/calc-spatial-on-host): use this when you need manual ROI spatial measurement instead of detection-driven triangulation

## Validation

- `Run:` `python3 main.py`
- `Standalone run:` `oakctl app run .`
- `Success looks like:` the Visualizer shows left, right, and combined views with face boxes, keypoints, disparity lines, and measurement text
- `Common failure meaning:` the stereo camera topology is missing, the YuNet model bundle is unavailable, or left/right detections are not pairing well enough for triangulation

- Run `python3 -m unittest discover -s tests -p test_rectified_geometry.py` from the repository root for known-depth/off-axis synthetic geometry and invalid correspondence regressions. Validate real scale with measured distances; an office scene alone does not establish accuracy.
