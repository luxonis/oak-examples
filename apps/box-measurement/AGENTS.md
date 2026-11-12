# AGENTS.md

## Summary

This is the RVC4 standalone frontend/backend app for measuring boxes on a flat support surface such as a conveyor belt, using stereo neural depth, instance segmentation and tracking with an IMU-checked support-plane calibration. Use it when you need per-box dimensions, volume, saved events with video clips, and a reusable box-measurement node set.

## Use This Example When

- You need box dimensions and volume on a conveyor or other flat surface, with per-box tracking and aggregated measurements.
- You want a reusable support-plane calibration flow (RANSAC plane candidates, gravity check from the IMU, user confirmation, persistence across restarts).
- You need a frontend/backend app that stores events (SQLite + images + video clips), keeps a rolling continuous recording, and exports archives.
- You want composable box-measurement DepthAI host nodes (`BoxDetector`, `BoxDimensioner`, `BoxMeasurer`, `SupportPlaneCalibrator`) to reuse in another pipeline.

## Do Not Use This Example When

- You only need a minimal box-measurement script with the DepthAI Visualizer; use `depth-measurement/measurement-3d/box-measurement` instead.
- You need RVC2 or peripheral (host) mode support.
- You only have a single-camera device such as OAK 4 S; depth comes from a stereo pair.
- You need to measure arbitrary objects selected by clicking rather than boxes on a plane.

## Quick Facts

- `Category:` `apps/box-measurement`
- `Shape:` `frontend`
- `Primary task:` box detection, tracking and L × W × H / volume measurement against a support plane
- `Entrypoint:` [backend/src/main.py](backend/src/main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` [frontend/src/App.tsx](frontend/src/App.tsx)
- `Runs on:` RVC4 standalone only (OAK 4 D, Pro or non-Pro)
- `Requires:` CAM_A, CAM_B and CAM_C; IMU accelerometer; static frontend build; Python 3.11 base image (`luxonis/oakapp-base:1.4.0-py311`)
- `Input:` live color camera, stereo pair through `NeuralDepth`, raw accelerometer
- `Output:` H.264 color stream, box annotations, support-surface preview point cloud, saved measurement events and continuous recording chunks under `OAKAGENT_STORAGE_SHARED`
- `Models:` `luxonis/box-instance-segmentation:512x320` from the model zoo; `NEURAL_DEPTH_768X480` from `dai.DeviceModelZoo`
- `Visualizer / UI:` custom static frontend served through the oakapp container stack; backend services on `dai.RemoteConnection`

## Read First

- [backend/src/app.py](backend/src/app.py): app lifecycle, frontend service registration, pipeline restart on settings change
- [backend/src/depthai_pipeline/init_pipeline.py](backend/src/depthai_pipeline/init_pipeline.py): full pipeline wiring
- [backend/src/config.py](backend/src/config.py): model names, resolutions, storage path
- [backend/src/solutions_sdk/box_measurement/__init__.py](backend/src/solutions_sdk/box_measurement/__init__.py): the reusable box-measurement node and message API
- [backend/src/solutions_sdk/box_measurement/node/box_measurer.py](backend/src/solutions_sdk/box_measurement/node/box_measurer.py): detector + dimensioner composite node
- [backend/src/solutions_sdk/box_measurement/node/support_plane_calibrator.py](backend/src/solutions_sdk/box_measurement/node/support_plane_calibrator.py): plane candidate discovery and verification
- [backend/src/services/support_plane_controller.py](backend/src/services/support_plane_controller.py): app-side calibration state, persistence and candidate selection
- [backend/src/settings/settings.py](backend/src/settings/settings.py): user-facing settings model
- [frontend/src/calibration/CalibrationPage.tsx](frontend/src/calibration/CalibrationPage.tsx): calibration UI flow
- [oakapp.toml](oakapp.toml): container, frontend build and base image

## Architecture

- `backend/src/solutions_sdk/box_measurement/` is a self-contained SDK of DepthAI host nodes and message types. It imports nothing from the rest of the app.
  - `BoxDetector` runs the instance-segmentation model and tracks boxes.
  - `BoxDimensioner` fits cuboids to each box's points relative to the active support plane and aggregates dimensions per track (component-wise median).
  - `BoxMeasurer` composes the two and outputs `BoxMeasurements`.
  - `SupportPlaneCalibrator` finds support-plane candidates from the organized point cloud and checks them against gravity from the IMU.
- The app layer (`depthai_pipeline/`, `services/`, `api/`, `database/`, `settings/`) turns measurement observations into measurement events, saves media, runs cleaners and serves the frontend.
- `App` owns one `dai.Pipeline` at a time and recreates it when settings change.

## Data Flow

- `CAM_B + CAM_C -> NeuralDepth -> ImageAlign (to 512x320 color) -> RGBD -> organized point cloud`
- `CAM_A -> ImageManip 512x320 BGR -> BoxMeasurer (color + point cloud) -> BoxMeasurements -> visualizer "Detections"`
- `point cloud + IMU -> SupportPlaneCalibrator -> SupportPlaneController -> active plane pushed into BoxMeasurer`
- `BoxMeasurements -> MeasurementEventEmitter -> MeasurementEventSaver (MJPEG snapshot + H.264 clip) -> SQLite + files`
- `CAM_A NV12 -> H.264 -> ContinuousRecorder (rolling chunks) and visualizer "Color stream"`

## Modification Guide

- `Safe to change:` settings defaults, frontend layout, resolutions in [backend/src/config.py](backend/src/config.py) (keep the 512x320 measurement grid in sync with the model), event retention
- `Requires care:` support-plane persistence format ([backend/src/util/support_plane_store.py](backend/src/util/support_plane_store.py)), service names and payloads shared with [frontend/src/backend/](frontend/src/backend/), event database schema
- `Likely to break if changed blindly:` point-cloud size/units passed to `BoxMeasurer` and `SupportPlaneCalibrator`, the plane sign/orientation convention, depthai / depthai-nodes / open3d version pins

## Common Adaptations

- `To reuse measurement in another pipeline:` copy [backend/src/solutions_sdk/](backend/src/solutions_sdk/) and wire `BoxMeasurer` + `SupportPlaneCalibrator` as in [backend/src/depthai_pipeline/init_pipeline.py](backend/src/depthai_pipeline/init_pipeline.py)
- `To change what a measurement event means:` start in [backend/src/depthai_pipeline/node/measurement_event_emitter.py](backend/src/depthai_pipeline/node/measurement_event_emitter.py)
- `To add a setting:` extend [backend/src/settings/settings.py](backend/src/settings/settings.py) and [frontend/src/settings/settingsSchema.ts](frontend/src/settings/settingsSchema.ts)

## Constraints

- RVC4 standalone only; the app exits with `UnsupportedDeviceError` if any of CAM_A, CAM_B or CAM_C is missing.
- Nothing is measured until a support plane is confirmed in the Calibration page; recalibrate after moving the camera.
- The IR dot projector is enabled when present; without it depth on plain surfaces is noisier.
- Pinned to `depthai==3.11.0`, `depthai-nodes==0.7.0`, `open3d==0.18` on Python 3.11 in the container.
- Any settings change restarts the whole pipeline; only the detection confidence threshold is applied live.

## Non-Obvious Repo Conventions

- The standalone runnability tests discover this app through `oakapp.toml` + `backend/src/main.py` and wait for the `Pipeline started.` log in [backend/src/app.py](backend/src/app.py). Peripheral and RVC2 runs are excluded in `tests/constants.py`.
- Backend unit tests live in [backend/tests/](backend/tests/) and run without a device: [backend/tests/device_lookup.py](backend/tests/device_lookup.py) patches the depthai-nodes device lookup. Lint and type-check config is in [backend/pyproject.toml](backend/pyproject.toml) and [backend/requirements-dev.txt](backend/requirements-dev.txt).

## Related Examples

- [depth-measurement/measurement-3d/box-measurement](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/measurement-3d/box-measurement): the minimal script version of box measurement with host-side cuboid fitting
- [apps/object-volume-measurement-3d](https://github.com/luxonis/oak-examples/tree/main/apps/object-volume-measurement-3d): click-to-select object volume measurement
- [apps/data-collection](https://github.com/luxonis/oak-examples/tree/main/apps/data-collection): another standalone frontend/backend app with service-driven configuration

## Validation

- `Run:` `oakctl app run .`
- `Success looks like:` the frontend shows the color stream; after confirming a support surface on the Calibration page, boxes passing the camera get dimensions overlaid and appear as events with snapshots and clips
- `Common failure meaning:` a non-stereo device (`UnsupportedDeviceError`), no plane confirmed yet, the static frontend was not built, or model zoo download failed on first run
- `Unit tests:` from [backend/](backend/), on Python 3.11 with [backend/requirements.txt](backend/requirements.txt) installed: `PYTHONPATH=src:tests python -m unittest discover -s tests -t tests`
