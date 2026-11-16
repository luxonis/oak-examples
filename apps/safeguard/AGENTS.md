# AGENTS.md

## Summary

Machine-Mounted Person Proximity Alert is an RVC4 example. Camera-relative zones use person segmentation, depth, and IMU; optional point-cloud obstacle detection and a frontend show live alerts.

## Use This Example When

- You need person proximity alerts in front of a machine-mounted RVC4 camera, with warning and danger zones configured for its mounting position.
- You want a standalone frontend/backend reference with annotated streams and live controls.
- You want to add an optional support-plane obstacle path to a person alert pipeline.
- You want a working example of depthai-nodes `AutoSupportPlane`, the hands-off automatic support plane calibration.

## Do Not Use This Example When

- You need recorded alerts, persistent settings, a database, LED relay control, or certified safety behavior.
- Your device lacks RGB, stereo, or IMU sensors, or you need a peripheral-mode example.

## Quick Facts

- `Category:` `apps/safeguard`
- `Shape:` `frontend`
- `Primary task:` machine-mounted, camera-relative person proximity alerts with optional generic obstacle detection
- `Entrypoint:` [backend/src/main.py](backend/src/main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` [frontend/src/App.tsx](frontend/src/App.tsx)
- `Runs on:` RVC4 standalone only
- `Requires:` RGB, stereo, and IMU sensors; a built static frontend; bundled person segmentation model
- `Input:` RGB preview, depth selected by the Depth node, 50 Hz raw accelerometer, and frontend settings
- `Output:` H.264 `Video` preview and its `Annotations` overlay; optional `Occupancy Grid`, `Support Plane Status`, and `Point Cloud` topics
- `Models:` bundled Zoo `luxonis/yolov8-instance-segmentation-nano:coco-512x288`, filtered to person class
- `Visualizer / UI:` custom HTTPS frontend built on `@luxonis/depthai-viewer-common` and `@luxonis/ui-components` with Tailwind, with raw DepthAI Visualizer on port 8082

## Read First

- [README.md](README.md): behavior, controls, and standalone run instructions.
- [backend/src/depthai_pipeline/init_pipeline.py](backend/src/depthai_pipeline/init_pipeline.py): camera, model, depth, IMU, and topic wiring.
- [backend/src/main.py](backend/src/main.py): service registration and pipeline restart lifecycle.
- [backend/src/settings/settings.py](backend/src/settings/settings.py): validated runtime settings and startup defaults.
- [frontend/src/App.tsx](frontend/src/App.tsx): live stream layout and the sidebar's device connection status.
- [frontend/src/settings/SettingsForm.tsx](frontend/src/settings/SettingsForm.tsx): live controls.

## Architecture

- RGB passes through a bundled instance segmentation model and native `ImgDetectionsFilter` to keep people. DepthAI's `ObjectTracker` assigns track IDs; `TrackletSegmentationMatcher` attaches the corresponding masks.
- The `Depth` node selects the backend automatically. Its depth output is aligned to person masks. `SegmentationDangerEvaluator` uses the IMU to rotate depth points into a gravity-aligned frame before testing warning and danger zones.
- Pipeline initialisation builds an RGBD point cloud from a 640 × 360 RGB camera output and aligned depth and passes it, with the IMU stream, into `PointCloudObjectDetectionNode`. That composite node runs depthai-nodes `AutoSupportPlane` in continuous mode, which finds the support plane automatically and keeps re-verifying it against gravity. `SupportPlaneSegmenter` turns each `AutoSupportPlaneResult` into per-frame data: it splits every frame's points into support plane and obstacle points at 45 mm, rotates them into a frame built from the support plane's normal, and publishes a `SupportPlaneStatus`. A result with `passed=False` means no valid support plane, so obstacle assessment stops. The occupancy grid groups obstacle points in a polar grid and evaluates obstacles against the same zones. The composite node publishes obstacles, the support plane point cloud, bird's-eye view, and support plane status annotations.
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

- This app is intended for RVC4 standalone mode with RGB, stereo, and IMU hardware. On any other platform, `init_pipeline()` raises `RuntimeError` at startup, before it creates any node.
- Preserve alignment between segmentation masks and depth, and preserve sequence and timestamp metadata passed between host nodes.
- RVC4 permits at most three outputs per camera. With generic object detection enabled, CAM_A already uses three: the 1080p model and tracker input, the NV12 preview for the H.264 encoder, and the RGB output for the point cloud. Reuse one of them rather than adding another `Camera.requestOutput()`.
- Settings are process-local; alerts and video are not recorded.
- The optional point-cloud path uses Open3D through the depthai-nodes `box-measurement` extra and can be costly. Support plane state is held only in the running pipeline.
- `init_pipeline.py` sets the support plane settings and passes them into `PointCloudObjectDetectionNode.build()`: `SUPPORT_PLANE_CALIBRATION` and the 45 mm `SUPPORT_PLANE_DIST_THR_MM` split threshold. `AutoSupportPlane` uses the default `PlaneCalibrationConfig` except for `max_calibration_attempts=10`. Without that cap a failed refit searches indefinitely, never reports `passed=False`, and the lost support plane stays valid. If a real floor is rejected, widen `max_gravity_angle_deg` before changing anything else.
- `AutoSupportPlaneResult` and `SupportPlaneStatus` are Python `Buffer` subclasses and only travel between host nodes.
- The `Video` topic is H.264, and the browser decodes it only in a secure context (HTTPS or localhost). The standalone UI is served over HTTPS; over plain HTTP from another host the stream stays blank.
- The frontend uses the same stack as the other frontend examples: `@luxonis/ui-components` controls, Tailwind classes with its theme tokens, and Biome. `react` and `react-dom` stay pinned to the exact version `@luxonis/depthai-viewer-common` declares as its peer.

## Non-Obvious Repo Conventions

- Native tracking supplies IDs, but instance masks are indexed by detection. `TrackletSegmentationMatcher` pairs them by same-frame box overlap and can reuse a cached mask for an active track.
- Every pipeline start, including the restart after applying settings, searches for the support plane afresh; no plane is carried over. Obstacle detection shows "plane invalid" until the search finds the floor.
- Stereo autocalibration comes from DepthAI's implicit `AutoCalibration` node (`ON_START` by default, overridable with `DEPTHAI_AUTOCALIBRATION`). Do not create an `AutoCalibration` node or call `setAutoCalibrationMode`; either disables the implicit node or the env-var override.
- The bundled model descriptor is resolved through the DepthAI Zoo for the connected device platform. Keep the YAML under `backend/src/depthai_models/` for OAK App packaging.

## Related Examples

- [apps/object-volume-measurement-3d](https://github.com/luxonis/oak-examples/tree/main/apps/object-volume-measurement-3d): custom frontend and ground-aligned 3D processing.
- [neural-networks/object-detection/human-machine-safety](https://github.com/luxonis/oak-examples/tree/main/neural-networks/object-detection/human-machine-safety): another proximity alert example.

## Validation

- `Run:` `oakctl app run .` from this directory with an RVC4 device connected. To check the frontend without a device, run `npm ci && npm run build && npm run lint` in `frontend/`.
- `Success looks like:` `Pipeline started.` appears in the log, the HTTPS frontend shows the `Video` stream with its `Annotations` overlay, and applying settings restarts the pipeline with the new values. With generic object detection enabled, `Occupancy Grid`, `Support Plane Status`, and `Point Cloud` appear, and the support plane turns valid once the floor is in view.
- `Common failure meaning:` a `RuntimeError` at startup means the device is not RVC4; a settings panel stuck on "Loading settings" means the backend crashed or never registered its services; a blank `Video` stream means the page is not in a secure context; a support plane that stays invalid means the floor is out of view or failed the gravity check.
