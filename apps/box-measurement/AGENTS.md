# AGENTS.md

## Summary

RVC4 standalone app for live box dimensioning on a support plane, built on depthai-nodes box-measurement nodes, with a support plane calibration and measurement frontend. Uses stereo depth, segmentation, tracking, IMU.

## Use This Example When

- You need live box dimensions and volume on a conveyor or other flat support plane, with per-box tracking and aggregated measurements.
- You want a reusable support plane calibration flow: RANSAC support plane candidates, a gravity check from the IMU, candidate cycling, operator confirmation and a ± distance offset.
- You want a worked wiring of the depthai-nodes `BoxMeasurer` and `SupportPlaneCalibrator` nodes to reuse in another pipeline.
- You want a small custom frontend on `@luxonis/ui-components` and Tailwind that switches views from polled backend state instead of routes.

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
- `Entrypoint:` [backend/src/main.py](backend/src/main.py), started by the `oakapp.toml` `entrypoint` as `/entrypoint.sh python3.11 -u /app/backend/src/main.py` (no wrapper script)
- `Standalone path:` [oakapp.toml](oakapp.toml), identifier `com.example.apps.box-measurement`, `app_version` `1.0.0`
- `Frontend:` [frontend/src/App.tsx](frontend/src/App.tsx); React 19 + Vite, `@luxonis/depthai-viewer-common` and `@luxonis/depthai-pipeline-lib` 4.0.0, `@luxonis/ui-components` with Tailwind 4, Biome for lint and format
- `Runs on:` RVC4 standalone only (OAK 4 D, Pro or non-Pro)
- `Requires:` CAM_A, CAM_B and CAM_C; IMU accelerometer; static frontend build; Python 3.11 base image (`luxonis/oakapp-base:1.4.0-py311`); internet on first start for the model download
- `Input:` live color camera, stereo pair through `NeuralDepth`, raw accelerometer
- `Output:` H.264 color stream, box annotations and a support plane preview point cloud; nothing is written to device storage
- `Models:` `luxonis/box-instance-segmentation:512x320`, downloaded from the model zoo at runtime by `BoxMeasurer`; `NEURAL_DEPTH_768X480` from `dai.DeviceModelZoo`
- `Visualizer / UI:` custom static frontend served through the oakapp container stack; backend services on `dai.RemoteConnection`

## Read First

- [backend/src/app.py](backend/src/app.py): app lifecycle, the eight frontend services, the run loop
- [backend/src/depthai_pipeline/init_pipeline.py](backend/src/depthai_pipeline/init_pipeline.py): full pipeline wiring and visualizer topics
- [backend/src/config.py](backend/src/config.py): model names, resolutions, frame rate and default detection confidence
- [backend/src/services/support_plane_controller.py](backend/src/services/support_plane_controller.py): app-side support plane calibration state, candidate selection and distance offset
- [frontend/src/App.tsx](frontend/src/App.tsx): picks the support plane calibration or measurement view from the polled support plane calibration state
- [frontend/src/supportPlaneCalibration/SupportPlaneCalibrationView.tsx](frontend/src/supportPlaneCalibration/SupportPlaneCalibrationView.tsx) and [frontend/src/MeasurementView.tsx](frontend/src/MeasurementView.tsx): the two views
- [oakapp.toml](oakapp.toml): identifier, entrypoint, container, frontend build and base image

## Architecture

- The box nodes and messages come from depthai-nodes (`depthai-nodes[box-measurement]`, see Constraints), not app code. The app imports `BoxMeasurer`, `SupportPlaneCalibrator` and `PlaneCalibrationConfig` from `depthai_nodes.node` and the support plane messages (`SupportPlane`, `SupportPlaneCandidate`, `SupportPlaneCalibrationControl`, `SupportPlaneCalibrationResult`, `CalibrationOutcome`) from `depthai_nodes.message`.
  - `BoxMeasurer` downloads and runs the instance-segmentation model, tracks boxes, fits cuboids relative to the active support plane and outputs `BoxMeasurements`.
  - `SupportPlaneCalibrator` finds support plane candidates in the organized point cloud and checks them against gravity from the IMU.
- The app layer:
  - `depthai_pipeline/` wires the pipeline and holds the `SupportPlanePreview` node.
  - `services/support_plane_controller.py` runs the support plane calibration states `SEARCHING → AWAITING_CONFIRMATION → CONFIRMED`, pushes the confirmed support plane, shifted by the distance offset, into `BoxMeasurer`, and reports status.
  - `api/request_handler.py` registers every service with pydantic-validated requests and responses; a failed validation or a raised exception becomes `{"error": "..."}`.
- `App` builds one `dai.Pipeline` at startup and runs it until the pipeline stops, `SIGINT`/`SIGTERM` arrives, or the remote connection sends `q`. There is no pipeline restart.
- Registered services: `getDetectionConfidenceThreshold`, `setDetectionConfidenceThreshold`, `getSupportPlaneCalibrationStatus`, `confirmSupportPlane`, `retrySupportPlaneCalibration`, `selectSupportPlaneCandidate`, `setSupportPlanePreviewActive`, `setSupportPlaneDistanceOffset`.
- The frontend is one page built from `@luxonis/ui-components` and Tailwind classes. Without a confirmed support plane it shows the support plane calibration view (status, camera tilt and distance, candidate cycling, confirm/restart, `Support plane preview` stream; the preview runs only while this view is shown). With one it shows the measurement view (`Color stream` + `Detections`, and a toolbar with the **Distance offset** and **Detection settings** panels and **Recalibrate**).
- The toolbar panels use [frontend/src/components/ToolbarPanel.tsx](frontend/src/components/ToolbarPanel.tsx), a button that drops a panel below itself and closes on Escape or an outside click, because ui-components has no popover. Reuse it for a new toolbar setting.
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
- `Requires care:` service names and payloads shared with [frontend/src/backend/](frontend/src/backend/), [frontend/src/supportPlaneCalibration/useSupportPlaneCalibration.tsx](frontend/src/supportPlaneCalibration/useSupportPlaneCalibration.tsx) and [frontend/src/detection/useDetectionConfidenceThreshold.tsx](frontend/src/detection/useDetectionConfidenceThreshold.tsx); the support plane calibration state names mirrored in [frontend/src/supportPlaneCalibration/supportPlaneCalibrationState.ts](frontend/src/supportPlaneCalibration/supportPlaneCalibrationState.ts); the visualizer topic names in [frontend/src/streamTopics.ts](frontend/src/streamTopics.ts), used by both views
- `Version pins:` the Luxonis frontend packages (`@luxonis/depthai-viewer-common` and `@luxonis/depthai-pipeline-lib` 4.0.0, `@luxonis/ui-components` 1.3.9, `@luxonis/ui-utils` 1.0.7) and `react` / `react-dom` are pinned exactly in [frontend/package.json](frontend/package.json), matching the other apps; bump them together with those apps. Dev tools keep caret ranges. Update `package-lock.json` with every change.
- `Likely to break if changed blindly:` point-cloud size/units passed to `BoxMeasurer` and `SupportPlaneCalibrator`, the plane sign/orientation convention, the depthai and depthai-nodes pins in [backend/requirements.txt](backend/requirements.txt) and the matching apt step in [oakapp.toml](oakapp.toml)

## Common Adaptations

- `To reuse measurement in another pipeline:` install `depthai-nodes[box-measurement]` at the version in [backend/requirements.txt](backend/requirements.txt) and wire `BoxMeasurer` + `SupportPlaneCalibrator` as in [backend/src/depthai_pipeline/init_pipeline.py](backend/src/depthai_pipeline/init_pipeline.py)
- `To act on measurements (log, store, forward):` read `BoxMeasurements` from `box_measurement.out` in [backend/src/depthai_pipeline/init_pipeline.py](backend/src/depthai_pipeline/init_pipeline.py) with a host node or output queue
- `To add a live control:` register a service in [backend/src/app.py](backend/src/app.py) with `add_request_handler`, define it in the frontend like [frontend/src/detection/useDetectionConfidenceThreshold.tsx](frontend/src/detection/useDetectionConfidenceThreshold.tsx), and put its UI in a `ToolbarPanel` like [frontend/src/detection/DetectionSettingsButton.tsx](frontend/src/detection/DetectionSettingsButton.tsx)
- `To change the frame rate:` edit `FPS` in [backend/src/config.py](backend/src/config.py)

## Constraints

- RVC4 standalone only; the app exits with `UnsupportedDeviceError` if any of CAM_A, CAM_B or CAM_C is missing.
- The segmentation model is downloaded at runtime on first start, not at build time, so the device needs internet then. `BoxMeasurer` hardcodes the model and takes none from outside, so the app has no `depthai_models` YAML or `oakapp.toml` key.
- Support plane calibration runs after every app start; nothing is measured until a support plane is confirmed. The confirmed support plane is not saved, so a camera moved while the app was off never measures against a stale support plane. Repeat support plane calibration (**Recalibrate**) after moving the camera.
- The distance offset can only be set once a support plane is confirmed, so its control lives in the measurement view; it resets on support plane calibration and on restart.
- The detection confidence threshold resets to `DEFAULT_DETECTION_CONFIDENCE_THRESHOLD` on every start.
- The IR dot projector is enabled when present; without it depth on plain surfaces is noisier.
- Python dependencies are pinned in [backend/requirements.txt](backend/requirements.txt): `depthai==3.11.0` and `depthai-nodes[box-measurement]==0.8.0` from PyPI, on Python 3.11 in the container. open3d comes in through the depthai-nodes `box-measurement` extra; the app doesn't import it.
- [oakapp.toml](oakapp.toml) apt-installs `libgfortran5 libegl1` because the open3d wheel links them; change them together with the open3d version.

## Non-Obvious Repo Conventions

- The standalone runnability tests discover this app through `oakapp.toml` + `backend/src/main.py` and wait for the `Pipeline started.` log in [backend/src/app.py](backend/src/app.py). Peripheral and RVC2 runs are excluded in `tests/constants.py`.
- The frontend checks are `npm run build` (runs `tsc -b`, then `vite build`) and `npm run lint` (Biome, configured in [frontend/biome.json](frontend/biome.json)) in [frontend/](frontend/); `npm run lint:fix` applies Biome's fixes and formatting (tabs).
- Use these terms in code, UI and docs:
  - **Support plane**: the flat surface boxes rest on, such as a conveyor belt or table; heights and distances are measured from it. Not "support surface", "ground plane" or "floor".
  - **Support plane candidate**: a flat surface found during support plane calibration that might be the support plane; the operator confirms one of them. Not "plane candidate" or "surface candidate".
  - **Support plane calibration**: finding the support plane candidates and having the operator confirm one as the support plane; repeated after every app start and whenever the camera moves. Not "plane calibration".
  - **Distance offset**: a signed distance the operator adds to the camera's detected distance from the support plane, to correct box heights that come out consistently too high or too low. Not "distance correction" or "height offset".
- Qualify "calibration" as support plane calibration, since bare "calibration" means camera calibration elsewhere in this repo; short button labels on a screen already titled "Support plane calibration", such as **Recalibrate** and **Restart calibration**, are the exception.

## Related Examples

- [depth-measurement/measurement-3d/box-measurement](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/measurement-3d/box-measurement): the minimal script version of box measurement with host-side cuboid fitting
- [apps/object-volume-measurement-3d](https://github.com/luxonis/oak-examples/tree/main/apps/object-volume-measurement-3d): click-to-select object volume measurement
- [apps/data-collection](https://github.com/luxonis/oak-examples/tree/main/apps/data-collection): another standalone frontend/backend app with service-driven configuration

## Validation

- `Run:` `oakctl app run .`
- `Success looks like:` the frontend opens on the support plane calibration view with the `Support plane preview`; after confirming a support plane it switches to the color stream, and boxes passing the camera get L × W × H and volume overlaid
- `Common failure meaning:` a non-stereo device (`UnsupportedDeviceError`), no support plane confirmed yet, the static frontend was not built, or the model download failed on first start
