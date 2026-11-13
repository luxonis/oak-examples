# AGENTS.md

## Summary

SafeGuard is an RVC4 proximity alert example using person segmentation, automatic depth selection, and IMU gravity for warning and danger zones. It has optional point-cloud obstacle detection and a custom frontend.

## Use This Example When

- You need person proximity alerts with configurable warning and danger zones on an RVC4 device.
- You want a standalone frontend/backend reference with annotated streams and live controls.
- You want to add an optional support-plane obstacle path to a person alert pipeline.
- You want a working example of depthai-nodes `AutoSupportPlane`, the hands-off automatic support plane calibration.

## Do Not Use This Example When

- You need recorded alerts, persistent settings, a database, LED relay control, or certified safety behavior.
- Your device lacks RGB, stereo, or IMU sensors, or you need a peripheral-mode example.

## Quick Facts

- `Category:` `apps/safeguard`
- `Shape:` `frontend`
- `Primary task:` person proximity alerts with optional generic obstacle detection
- `Entrypoint:` [backend/src/main.py](backend/src/main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` [frontend/src/App.tsx](frontend/src/App.tsx)
- `Runs on:` RVC4 standalone only
- `Requires:` RGB, stereo, and IMU sensors; a built static frontend; bundled person segmentation model
- `Input:` RGB preview, depth selected by the Depth node, 50 Hz raw accelerometer, and frontend settings
- `Output:` `color` preview and `danger` annotations; optional `obstacle_annotations`, `grid`, `grid_annotations`, and `pcl` topics
- `Model:` bundled Zoo `luxonis/yolov8-instance-segmentation-nano:coco-512x288`, filtered to person class
- `Visualizer / UI:` custom HTTPS frontend, with raw DepthAI Visualizer on port 8082

## Read First

- [README.md](README.md): behavior, controls, and standalone run instructions.
- [backend/src/depthai_pipeline/init_pipeline.py](backend/src/depthai_pipeline/init_pipeline.py): camera, model, depth, IMU, and topic wiring.
- [backend/src/main.py](backend/src/main.py): service registration and pipeline restart lifecycle.
- [backend/src/settings/settings.py](backend/src/settings/settings.py): validated runtime settings and startup defaults.
- [frontend/src/App.tsx](frontend/src/App.tsx): live stream layout.
- [frontend/src/settings/SettingsForm.tsx](frontend/src/settings/SettingsForm.tsx): live controls.

## Architecture

- RGB passes through a bundled instance segmentation model and native `ImgDetectionsFilter` to keep people. DepthAI's `ObjectTracker` assigns track IDs; `TrackletSegmentationMatcher` attaches the corresponding masks.
- The `Depth` node selects the backend automatically. Its depth output is aligned to person masks. `SegmentationDangerEvaluator` uses the IMU to rotate depth points into a gravity-aligned frame before testing warning and danger zones.
- Pipeline initialisation builds an RGBD point cloud from the preview and aligned depth and passes it, with the IMU stream, into `PointCloudObjectDetectionNode`. That composite node runs depthai-nodes `AutoSupportPlane` in continuous mode, which finds the support plane automatically and keeps re-verifying it against gravity. `SupportPlaneSegmenter` turns each `AutoSupportPlaneResult` into per-frame data: it splits every frame's points into support plane and obstacle points at 45 mm, rotates them into a frame built from the support plane's normal, and publishes a `SupportPlaneStatus`. A result with `passed=False` means no valid support plane, so obstacle assessment stops. The occupancy grid groups obstacle points in a polar grid and evaluates obstacles against the same zones. The composite node publishes support plane points, obstacle boxes, bird's-eye view, and support plane status annotations.
- `DangerClassifier` combines available assessments and applies temporal alert transitions. `DangerVisualizer` publishes person and alert annotations.
- The frontend calls `getSettings` and `updateSettings`. Applying settings rebuilds the pipeline.

## Data Flow

- `RGB -> person segmentation -> native person filter + tracker -> mask/track matching`
- `selected depth + IMU + tracked masks -> person zone assessment`
- `selected depth + RGB + IMU -> optional support plane and obstacle assessment`
- `assessments -> temporal classification -> live annotations -> frontend`

## Modification Guide

- `Safe to change:` zone defaults, alert timing, frontend labels, and panel layout.
- `Requires care:` model descriptor, person label filtering, segmentation/depth alignment, and camera intrinsics.
- `Likely to break if changed blindly:` the indexed mask-to-track association, sequence metadata shared by host nodes, or frontend service and topic names.

## Common Adaptations

- `To change zone defaults:` edit [backend/src/settings/settings.py](backend/src/settings/settings.py) and keep frontend validation in [frontend/src/settings/settingsSchema.ts](frontend/src/settings/settingsSchema.ts) aligned.
- `To change model or camera wiring:` edit [backend/src/depthai_pipeline/init_pipeline.py](backend/src/depthai_pipeline/init_pipeline.py) and the model declaration under `backend/src/depthai_models/`.
- `To change obstacle views:` edit [backend/src/depthai_pipeline/pointcloud_object_detection/node/occupancy_grid_visualization.py](backend/src/depthai_pipeline/pointcloud_object_detection/node/occupancy_grid_visualization.py).
- `To change frontend controls:` edit [frontend/src/settings/SettingsForm.tsx](frontend/src/settings/SettingsForm.tsx) and [frontend/src/App.tsx](frontend/src/App.tsx).

## Constraints

- This app is intended for RVC4 standalone mode with RGB, stereo, and IMU hardware.
- Preserve alignment between segmentation masks and depth, and preserve sequence and timestamp metadata passed between host nodes.
- RVC4 permits at most three outputs per camera. Reuse the 640 × 360 preview for the optional point cloud rather than adding another `Camera.requestOutput()`.
- Settings are process-local; alerts and video are not recorded.
- The optional point-cloud path uses Open3D through the depthai-nodes `box-measurement` extra and can be costly. Support plane state is held only in the running pipeline.
- `AutoSupportPlane` uses the default `PlaneCalibrationConfig` except for `max_calibration_attempts=10`. Without that cap a failed refit searches indefinitely, never reports `passed=False`, and the lost support plane stays valid. If a real floor is rejected, widen `max_gravity_angle_deg` before changing anything else.
- `AutoSupportPlaneResult` and `SupportPlaneStatus` are Python `Buffer` subclasses and only travel between host nodes.
- Encoded topics in the custom browser frontend require HTTPS or localhost; the standalone UI is served over HTTPS.

## Non-Obvious Repo Conventions

- Native tracking supplies IDs, but instance masks are indexed by detection. `TrackletSegmentationMatcher` pairs them by same-frame box overlap and can reuse a cached mask for an active track.
- Every pipeline start, including the restart after applying settings, searches for the support plane afresh; no plane is carried over. Obstacle detection shows "plane invalid" until the search finds the floor.
- The bundled model descriptor is resolved through the DepthAI Zoo for the connected device platform. Keep the YAML under `backend/src/depthai_models/` for OAK App packaging.

## Related Examples

- [apps/object-volume-measurement-3d](https://github.com/luxonis/oak-examples/tree/main/apps/object-volume-measurement-3d): custom frontend and ground-aligned 3D processing.
- [neural-networks/object-detection/human-machine-safety](https://github.com/luxonis/oak-examples/tree/main/neural-networks/object-detection/human-machine-safety): another proximity alert example.

## Validation

- `Run:` `python3 -m compileall -q apps/safeguard/backend/src` and `python3 scripts/validate_agents_docs.py` from the repository root.
- `Unit tests:` from `apps/safeguard/backend`, with [backend/requirements.txt](backend/requirements.txt) installed and no device: `PYTHONPATH=src:tests python -m unittest discover -s tests -t tests`. [backend/tests/test_obstacle_path.py](backend/tests/test_obstacle_path.py) drives `PointCloudObjectDetectionNode`, including the real `AutoSupportPlane`, in a host-only pipeline with synthetic point clouds and gravity (about 10 s, because continuous mode needs repeated failed checks 0.5 s apart); [backend/tests/device_lookup.py](backend/tests/device_lookup.py) lets depthai-nodes host nodes be created without a device.
- `Frontend:` run `npm ci && npm run build` in `apps/safeguard/frontend` with Node 22 or newer.
- `Device:` run `oakctl app run apps/safeguard --device 1` on a connected RVC4. Success means `Pipeline started.` appears, the HTTPS frontend shows `color` and `danger`, and settings apply. Enable generic object detection to check `obstacle_annotations`, `grid`, `grid_annotations`, and `pcl`.
