# AGENTS.md

## Summary

OAK4 parcel measurement with public depthai-nodes parcel detection, dimensioning, and support-plane calibration. A custom frontend shows tracked RGB boxes and dimensions and lets the operator select the support surface from calibration candidates.

## Use This Example When

- You need deterministic parcel measurement on a user-selected horizontal support plane.
- You need RGB bounding boxes labelled with temporary tracking IDs and length, width, and height.
- You need the evaluated capture profile from depthai-nodes PR 348.

## Do Not Use This Example When

- You need persistent parcel identity across occlusion or cameras.
- You need an RVC2 example, arbitrary object segmentation, or point-to-point measurement.
- You need guaranteed measurement accuracy without a scene-specific evaluation.

## Quick Facts

- `Entrypoint:` [main.py](main.py)
- `Geometry:` [geometry.py](geometry.py)
- `Domain state:` [domain.py](domain.py)
- `Frontend:` [frontend/index.html](frontend/index.html), [frontend/app.js](frontend/app.js)
- `Server:` [web.py](web.py), HTTP port 8082 and WebSocket `/ws`
- `Mode:` host plus OAK4 standalone packaging in [oakapp.toml](oakapp.toml)
- `Requires:` OAK4 RGB, stereo, processed accelerometer reports, and Python 3.12 host environment
- `Capture:` 10 FPS by default; unrectified RGB 2000 × 1500 NV12 and left/right 1280 × 800 GRAY8
- `Depth:` native NeuralDepth LARGE at 768 × 480, native organized PointCloud on host
- `Dependencies:` [requirements.txt](requirements.txt), immutable depthai-nodes PR 348 revision with parcel and box-measurement extras
- `Inspection topics:` RGB, Depth, Parcel overlay on RemoteConnection port 8765

## Read First

- [main.py](main.py) for capture, public node wiring, configuration updates, and frame/result joins.
- [geometry.py](geometry.py) for common-reference projection and IMU conversion.
- [domain.py](domain.py) for calibration lifecycle and one-to-one tracking associations.
- [web.py](web.py) for frontend commands and snapshots.
- [README.md](README.md) for operation and scene requirements.

## Architecture

Camera outputs use the evaluated unrectified image grids. Their native metadata includes delivered intrinsics, lens distortion, and poses in a shared reference frame. NeuralDepth performs its internal stereo processing and emits 768 × 480 depth. A native DEFAULT PointCloud node produces organized XYZ in the common calibration reference frame. Do not apply the cloud's source optical pose to those points again.

The device-backed capture pipeline contains `SupportPlaneCalibrator`. Its organized cloud is the native PointCloud output. Processed accelerometer specific force is rotated from RGB optical axes into the common reference using the RGB metadata pose. The calibrator receives upward specific force without negation.

The host-only parcel pipeline starts after the operator selects an actual support plane. `ParcelDetector.build(pointCloud, color, left, right, supportPlane)` initializes it. Later selections send `ParcelDetectorConfig(supportPlane=...)` through `inputConfig` immediately before the next admitted scene. The node retains that configuration, so no per-frame plane message is needed. Config updates are queued only when a scene is admitted, preventing unconsumed obsolete selections.

Parcel scenes preserve native image sequence counters and device timestamps. The detector's native host Sync handles independent counters. A finite cloud copy keeps the native cloud metadata and sequence. One in-flight scene retains its RGB and joins detection and measurement results by cloud sequence. Tracking adds temporary IDs to frame-local parcel candidates.

Common-reference points project through the inverse RGB pose, delivered intrinsics, and distortion model into the unrectified RGB grid. Candidate previews project plane inliers into RGB instead of reshaping the lower-resolution cloud mask.

## Constraints

- Import only names exported by `depthai_nodes.node` and `depthai_nodes.message`. Do not import frozen algorithms or node implementation internals.
- Parcel messages stay in one host process. They have no XLink or RemoteConnection serialization.
- Keep PointCloud DEFAULT coordinates, millimeters, calibrated translation, identity custom transform, and organized output. Do not set a different target coordinate system.
- The calibration cloud stays organized to 768 × 480. Detector input contains only finite, nonzero XYZ and retains the original cloud metadata.
- Keep raw RGB and mono inputs unrectified. Do not substitute NeuralDepth's rectified views or resize detector images.
- Capture defaults to 10 FPS. Processing throughput depends on the host and scene. `/api/state` and the frontend distinguish configured capture rate, observed source rate, and measurement throughput.
- Keep the camera fixed after plane selection. Recalibrate whenever the camera or support surface moves.
- Calibration attempts cannot overlap. Candidate selection carries a generation to reject stale clicks.
- Candidate IDs are frame-local. Never display them directly as temporal tracking IDs.
- Failed frames, no-fit results, and unknown heights are distinct outcomes. Do not replace missing dimensions with zeros.
- Keep local scene images under ignored `evidence/`.

## Related Examples

- [custom-frontend/raw-stream](https://github.com/luxonis/oak-examples/tree/main/custom-frontend/raw-stream) for a minimal custom frontend.
- [neural-networks/depth-estimation/neural-depth](https://github.com/luxonis/oak-examples/tree/main/neural-networks/depth-estimation/neural-depth) for native NeuralDepth configuration.
- [depth-measurement/measurement-3d/rgbd-pointcloud](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/measurement-3d/rgbd-pointcloud) for another native point-cloud pipeline.

## Validation

- Run `python3 -m unittest discover -s tests -v` in this directory.
- Run against an OAK4, trigger calibration, inspect previews, select the true support surface, and confirm matching RGB boxes with IDs and dimensions.
- Use `--evidence evidence` to save native camera/cloud metadata, selected plane, RGB, overlay, and structured results.
- Inspect RGB, Depth, and Parcel overlay with oakctl. Process startup alone does not validate measurement.
- Check independent image counters, distorted RGB projection, common-reference IMU rotation, repeated calibration, stale selections, and tracking despite candidate reordering.
