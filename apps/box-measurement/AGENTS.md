# AGENTS.md

## Summary

RVC4 standalone app for live box dimensioning on a calibrated support plane, built on the depthai-nodes box-measurement nodes, with a calibration and measurement frontend. Uses stereo depth, segmentation, tracking, IMU.

## Use This Example When

- You need live box dimensions and volume on a conveyor or other flat support plane, with per-box tracking and aggregated measurements.
- You want a reusable support-plane calibration flow: RANSAC plane candidates, a gravity check from the IMU, candidate cycling, user confirmation and a ± distance offset.
- You want a worked wiring of the depthai-nodes `BoxMeasurer` and `SupportPlaneCalibrator` nodes to reuse in another pipeline.
- You want a small custom frontend that switches views from polled backend state instead of routes.

## Do Not Use This Example When

- You only need a minimal box-measurement script with the DepthAI Visualizer; use `depth-measurement/measurement-3d/box-measurement` instead.
- You need to store, record or export measurements; this app only shows them live and writes nothing to device storage.
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
- `Output:` H.264 color stream, box annotations and a support-plane preview point cloud; nothing is written to device storage
- `Models:` `luxonis/box-instance-segmentation:512x320` from the model zoo; `NEURAL_DEPTH_768X480` from `dai.DeviceModelZoo`
- `Visualizer / UI:` custom static frontend served through the oakapp container stack; backend services on `dai.RemoteConnection`

## Read First

- [backend/src/app.py](backend/src/app.py): app lifecycle, the eight frontend services, the run loop
- [backend/src/depthai_pipeline/init_pipeline.py](backend/src/depthai_pipeline/init_pipeline.py): full pipeline wiring and visualizer topics
- [backend/src/config.py](backend/src/config.py): model names, resolutions, frame rate and default detection confidence
- [backend/src/services/support_plane_controller.py](backend/src/services/support_plane_controller.py): app-side calibration state, candidate selection and distance offset
- [frontend/src/App.tsx](frontend/src/App.tsx): picks the calibration or measurement view from the polled calibration state
- [frontend/src/calibration/CalibrationView.tsx](frontend/src/calibration/CalibrationView.tsx) and [frontend/src/MeasurementView.tsx](frontend/src/MeasurementView.tsx): the two views
- [oakapp.toml](oakapp.toml): container, frontend build and base image

## Architecture

- The box nodes and messages come from depthai-nodes (`depthai-nodes[box-measurement]`, see Constraints), not app code. The app imports `BoxMeasurer`, `SupportPlaneCalibrator` and `PlaneCalibrationConfig` from `depthai_nodes.node` and the support-plane messages (`SupportPlane`, `SupportPlaneCandidate`, `SupportPlaneCalibrationControl`, `SupportPlaneCalibrationResult`, `CalibrationOutcome`) from `depthai_nodes.message`.
  - `BoxMeasurer` runs the instance-segmentation model, tracks boxes, fits cuboids relative to the active support plane and outputs `BoxMeasurements`.
  - `SupportPlaneCalibrator` finds support plane candidates in the organized point cloud and checks them against gravity from the IMU.
- The app layer:
  - `depthai_pipeline/` wires the pipeline and holds the `SupportPlanePreview` node.
  - `services/support_plane_controller.py` runs the calibration states `SEARCHING → AWAITING_CONFIRMATION → CONFIRMED`, pushes the confirmed (offset-corrected) support plane into `BoxMeasurer`, and reports status.
  - `api/request_handler.py` registers every service with pydantic-validated requests and responses; a failed validation or a raised exception becomes `{"error": "..."}`.
- `App` builds one `dai.Pipeline` at startup and runs it until the pipeline stops, `SIGINT`/`SIGTERM` arrives, or the remote connection sends `q`. There is no pipeline restart.
- Registered services: `getDetectionConfidenceThreshold`, `setDetectionConfidenceThreshold`, `getSupportPlaneCalibrationStatus`, `confirmSupportPlane`, `retrySupportPlaneCalibration`, `selectSupportPlaneCandidate`, `setSupportPlanePreviewActive`, `setSupportPlaneDistanceOffset`. [backend/tests/test_app_services.py](backend/tests/test_app_services.py) pins this set.
- The frontend is one page. Without a confirmed support plane it shows the calibration view (status, camera tilt and distance, candidate cycling, confirm/restart, `Support plane preview` stream; the preview runs only while this view is shown). With one it shows the measurement view (`Color stream` + `Detections`, detection settings popover, distance correction, "Recalibrate").
- Frontend service calls go through TanStack Query + zod definitions in [frontend/src/backend/](frontend/src/backend/).

## Data Flow

- `CAM_B + CAM_C -> NeuralDepth -> ImageAlign (to 512x320 color) -> RGBD -> organized point cloud`
- `CAM_A -> ImageManip 512x320 BGR -> BoxMeasurer (color + point cloud) -> BoxMeasurements -> visualizer "Detections"`
- `point cloud + IMU -> SupportPlaneCalibrator -> SupportPlaneController -> confirmed support plane (+ distance offset) pushed into BoxMeasurer`
- `point cloud + SupportPlaneController -> SupportPlanePreview -> visualizer "Support plane preview"`
- `CAM_A NV12 -> H.264 -> visualizer "Color stream"`
- `frontend -> setDetectionConfidenceThreshold -> BoxMeasurer.setConfidenceThreshold` (applied live, kept in memory only)

## Modification Guide

- `Safe to change:` `FPS`, resolutions and the default confidence in [backend/src/config.py](backend/src/config.py) (keep the 512x320 measurement grid in sync with the model), frontend layout and wording
- `Requires care:` service names and payloads shared with [frontend/src/backend/](frontend/src/backend/), [frontend/src/calibration/useSupportPlaneCalibration.tsx](frontend/src/calibration/useSupportPlaneCalibration.tsx) and [frontend/src/detection/useDetectionConfidenceThreshold.tsx](frontend/src/detection/useDetectionConfidenceThreshold.tsx); the calibration state names mirrored in [frontend/src/calibration/calibrationState.ts](frontend/src/calibration/calibrationState.ts); the visualizer topic names used by both views
- `Likely to break if changed blindly:` point-cloud size/units passed to `BoxMeasurer` and `SupportPlaneCalibrator`, the plane sign/orientation convention, depthai / depthai-nodes / open3d version pins and the matching apt step in [oakapp.toml](oakapp.toml)

## Common Adaptations

- `To reuse measurement in another pipeline:` install `depthai-nodes[box-measurement]` (currently the git pin in [backend/requirements.txt](backend/requirements.txt)) and wire `BoxMeasurer` + `SupportPlaneCalibrator` as in [backend/src/depthai_pipeline/init_pipeline.py](backend/src/depthai_pipeline/init_pipeline.py)
- `To act on measurements (log, store, forward):` read `BoxMeasurements` from `box_measurement.out` in [backend/src/depthai_pipeline/init_pipeline.py](backend/src/depthai_pipeline/init_pipeline.py) with a host node or output queue
- `To add a live control:` register a service in [backend/src/app.py](backend/src/app.py) with `add_request_handler`, define it in the frontend like [frontend/src/detection/useDetectionConfidenceThreshold.tsx](frontend/src/detection/useDetectionConfidenceThreshold.tsx), and add the name to the pinned set in [backend/tests/test_app_services.py](backend/tests/test_app_services.py)
- `To change the frame rate:` edit `FPS` in [backend/src/config.py](backend/src/config.py)

## Constraints

- RVC4 standalone only; the app exits with `UnsupportedDeviceError` if any of CAM_A, CAM_B or CAM_C is missing.
- The support plane must be confirmed after every app start; nothing is measured until then. Calibration state is not saved, so a camera moved while the app was off never measures against a stale support plane. Recalibrate after moving the camera.
- The distance offset can only be set once a support plane is confirmed, so its control lives in the measurement view; it resets on recalibration and on restart.
- The detection confidence threshold resets to `DEFAULT_DETECTION_CONFIDENCE_THRESHOLD` on every start.
- The IR dot projector is enabled when present; without it depth on plain surfaces is noisier.
- `depthai-nodes[box-measurement]` is a git pin to a full commit SHA in [backend/requirements.txt](backend/requirements.txt), because no depthai-nodes release ships the box nodes yet. The pin is temporary and branch-only: replace it with a PyPI release that ships them before merging to `main`. The pinned SHA must stay fetchable from the public depthai-nodes repo.
- Pinned to `depthai==3.11.0` and `open3d==0.20.0` on Python 3.11 in the container. open3d comes in through depthai-nodes; the app doesn't import it.
- [oakapp.toml](oakapp.toml) apt-installs `libgfortran5 libegl1` because the open3d 0.20.0 wheel links them; change them together.

## Non-Obvious Repo Conventions

- The standalone runnability tests discover this app through `oakapp.toml` + `backend/src/main.py` and wait for the `Pipeline started.` log in [backend/src/app.py](backend/src/app.py). Peripheral and RVC2 runs are excluded in `tests/constants.py`.
- Backend unit tests live in [backend/tests/](backend/tests/) and run without a device: [backend/tests/device_lookup.py](backend/tests/device_lookup.py) patches the depthai-nodes device lookup, and the service tests patch `dai.RemoteConnection` with a fake that records registered services.
- The frontend has no unit tests; `npm run typecheck`, `npm run lint` and `npm run build` in [frontend/](frontend/) are the checks.
- Use "support plane" (the confirmed plane boxes are measured against) and "support plane candidate" (a plane the calibrator proposes before confirmation) in code, UI and docs, not "support surface", "ground plane" or "floor".

## Related Examples

- [depth-measurement/measurement-3d/box-measurement](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/measurement-3d/box-measurement): the minimal script version of box measurement with host-side cuboid fitting
- [apps/object-volume-measurement-3d](https://github.com/luxonis/oak-examples/tree/main/apps/object-volume-measurement-3d): click-to-select object volume measurement
- [apps/data-collection](https://github.com/luxonis/oak-examples/tree/main/apps/data-collection): another standalone frontend/backend app with service-driven configuration

## Validation

- `Run:` `oakctl app run .`
- `Success looks like:` the frontend opens on the calibration view with the `Support plane preview`; after confirming a support plane it switches to the color stream, and boxes passing the camera get L × W × H and volume overlaid
- `Common failure meaning:` a non-stereo device (`UnsupportedDeviceError`), no support plane confirmed yet, the static frontend was not built, or model zoo download failed on first run
- `Unit tests:` from [backend/](backend/), on Python 3.11 with only [backend/requirements.txt](backend/requirements.txt) installed (needs network and git for the depthai-nodes pin), no device: `PYTHONPATH=src:tests python -m unittest discover -s tests -t tests`
