# AGENTS.md

## Summary

RVC4 standalone app for live box dimensioning on a support plane, built on depthai-nodes box-measurement nodes, with a support plane calibration and measurement frontend. Uses stereo depth, segmentation, tracking, IMU.

## Use This Example When

- You need live box dimensions and volume on a conveyor or other flat support plane, with per-box tracking.
- You want an operator-confirmed support plane calibration flow: candidates checked against IMU gravity, candidate cycling, confirmation and a distance offset.
- You want a worked wiring of the depthai-nodes `BoxMeasurer` and `SupportPlaneCalibrator` nodes.
- You want a small frontend that switches views from polled backend state instead of routes.

## Do Not Use This Example When

- You only need a minimal box-measurement script with the DepthAI Visualizer; use `depth-measurement/measurement-3d/box-measurement`.
- You need to store, record or export measurements.
- You need RVC2, peripheral mode, or a single-camera device such as OAK 4 S.
- You need to measure arbitrary click-selected objects rather than boxes on a plane.

## Quick Facts

- `Category:` `apps/box-measurement`
- `Shape:` `frontend`
- `Primary task:` box detection, tracking and L × W × H / volume measurement against a support plane
- `Entrypoint:` [backend/src/main.py](backend/src/main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` [frontend/src/App.tsx](frontend/src/App.tsx)
- `Runs on:` RVC4 standalone only (OAK 4 D)
- `Requires:` CAM_A, CAM_B and CAM_C; IMU; static frontend build; internet on first start for the model download
- `Input:` color camera, stereo pair, accelerometer
- `Output:` `Color stream`, `Detections` and `Support plane preview` topics; nothing is written to device storage
- `Models:` `luxonis/box-instance-segmentation:512x320`, downloaded at runtime by `BoxMeasurer`; `NEURAL_DEPTH_768X480` from `dai.DeviceModelZoo`
- `Visualizer / UI:` custom static frontend

## Read First

- [backend/src/app.py](backend/src/app.py): lifecycle, frontend services and the run loop
- [backend/src/depthai_pipeline/init_pipeline.py](backend/src/depthai_pipeline/init_pipeline.py): pipeline wiring and visualizer topics
- [backend/src/services/support_plane_controller.py](backend/src/services/support_plane_controller.py): support plane calibration state, candidate selection and distance offset
- [backend/src/config.py](backend/src/config.py): neural depth model, camera resolutions, frame rate and default detection confidence
- [frontend/src/App.tsx](frontend/src/App.tsx), [frontend/src/supportPlaneCalibration/SupportPlaneCalibrationView.tsx](frontend/src/supportPlaneCalibration/SupportPlaneCalibrationView.tsx) and [frontend/src/MeasurementView.tsx](frontend/src/MeasurementView.tsx): view selection and the two views
- [oakapp.toml](oakapp.toml): container, frontend build and Python 3.11 base image

## Architecture

- `BoxMeasurer` and `SupportPlaneCalibrator` come from depthai-nodes (`depthai_nodes.node`, messages in `depthai_nodes.message`), not app code. `BoxMeasurer` downloads and runs the segmentation model, tracks boxes and fits cuboids against the active support plane. `SupportPlaneCalibrator` finds support plane candidates in the organized point cloud and checks them against gravity from the IMU.
- `SupportPlaneController` runs `SEARCHING → AWAITING_CONFIRMATION → CONFIRMED` and pushes the confirmed support plane, shifted by the distance offset, into `BoxMeasurer`.
- The `SupportPlanePreview` host node publishes the point cloud with a grid on the highlighted support plane, only while the support plane calibration view asks for it.
- [backend/src/api/request_handler.py](backend/src/api/request_handler.py) registers services with pydantic-validated requests and responses; failures become `{"error": "..."}`.
- One pipeline runs for the app's lifetime; it stops on pipeline stop, `SIGINT`/`SIGTERM`, or `q` from the remote connection.
- The frontend picks its view from the polled support plane calibration state: the support plane calibration view until a support plane is confirmed, then the measurement view with **Distance offset**, **Detection settings** and **Recalibrate** in its toolbar. Toolbar panels use [frontend/src/components/ToolbarPanel.tsx](frontend/src/components/ToolbarPanel.tsx), since ui-components has no popover. Service calls go through TanStack Query + zod in [frontend/src/backend/](frontend/src/backend/).

## Data Flow

- `CAM_B + CAM_C -> NeuralDepth -> ImageAlign (to 512x320 color) -> RGBD -> organized point cloud`
- `CAM_A -> ImageManip 512x320 BGR -> BoxMeasurer (color + point cloud) -> Detections`
- `point cloud + IMU -> SupportPlaneCalibrator -> SupportPlaneController -> confirmed support plane (+ distance offset) -> BoxMeasurer`
- `point cloud + SupportPlaneController -> SupportPlanePreview -> Support plane preview`
- `CAM_A NV12 -> H.264 -> Color stream`

## Modification Guide

- `Safe to change:` `FPS`, camera resolutions and the default confidence in [backend/src/config.py](backend/src/config.py); frontend layout and wording
- `Requires care:` service names and payloads shared by [backend/src/app.py](backend/src/app.py) and the frontend hooks in [frontend/src/supportPlaneCalibration/](frontend/src/supportPlaneCalibration/) and [frontend/src/detection/](frontend/src/detection/); state names mirrored in [frontend/src/supportPlaneCalibration/supportPlaneCalibrationState.ts](frontend/src/supportPlaneCalibration/supportPlaneCalibrationState.ts); topic names in [frontend/src/streamTopics.ts](frontend/src/streamTopics.ts); the Luxonis frontend packages and `react`, pinned exactly like in the other apps
- `Likely to break if changed blindly:` the 512x320 measurement grid hardcoded in `init_pipeline.py`, which must match the `BoxMeasurer` model; point-cloud size and units passed to the depthai-nodes nodes; the plane sign convention; the depthai and depthai-nodes pins and the matching apt step in [oakapp.toml](oakapp.toml)

## Common Adaptations

- `To reuse measurement in another pipeline:` install `depthai-nodes[box-measurement]` at the version in [backend/requirements.txt](backend/requirements.txt) and wire the nodes as in [backend/src/depthai_pipeline/init_pipeline.py](backend/src/depthai_pipeline/init_pipeline.py)
- `To act on measurements (log, store, forward):` read `BoxMeasurements` from `box_measurement.out` with a host node or output queue
- `To add a live control:` register a service with `add_request_handler` in [backend/src/app.py](backend/src/app.py), define it like [frontend/src/detection/useDetectionConfidenceThreshold.tsx](frontend/src/detection/useDetectionConfidenceThreshold.tsx), and put its UI in a `ToolbarPanel`

## Constraints

- RVC4 standalone only; the app exits with `UnsupportedDeviceError` if CAM_A, CAM_B or CAM_C is missing.
- `BoxMeasurer` hardcodes and downloads its model at runtime, so there is no `depthai_models` YAML.
- Support plane calibration runs after every start and nothing is measured until a support plane is confirmed. The support plane is not saved, so repeat support plane calibration after moving the camera.
- The distance offset can be set only after confirmation and resets on support plane calibration and restart. The detection confidence threshold resets on restart.
- Pins: `depthai==3.11.0` and `depthai-nodes[box-measurement]==0.8.0`, which pulls in open3d; the container apt-installs `libgfortran5 libegl1` for the open3d wheel.

## Non-Obvious Repo Conventions

- Peripheral and RVC2 test runs are excluded in `tests/constants.py`.
- Use these terms in code, UI and docs:
  - **Support plane**: the flat surface boxes rest on; heights and distances are measured from it. Not "ground plane" or "floor".
  - **Support plane candidate**: a plane found during support plane calibration that the operator may confirm.
  - **Support plane calibration**: finding candidates and confirming one; bare "calibration" means camera calibration elsewhere in this repo. Short button labels such as **Recalibrate** and **Restart calibration** are the exception.
  - **Distance offset**: a signed correction the operator adds to the camera's detected distance from the support plane. Not "height offset".

## Related Examples

- [depth-measurement/measurement-3d/box-measurement](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/measurement-3d/box-measurement): the minimal script version of box measurement with host-side cuboid fitting
- [apps/object-volume-measurement-3d](https://github.com/luxonis/oak-examples/tree/main/apps/object-volume-measurement-3d): click-to-select object volume measurement
- [apps/data-collection](https://github.com/luxonis/oak-examples/tree/main/apps/data-collection): another standalone frontend/backend app with service-driven configuration

## Validation

- `Run:` `oakctl app run .`
- `Success looks like:` the frontend opens on the support plane calibration view with the `Support plane preview`; after confirming a support plane it switches to the color stream, and boxes passing the camera get L × W × H and volume overlaid
- `Common failure meaning:` a non-stereo device (`UnsupportedDeviceError`), no support plane confirmed yet, the static frontend was not built, or the model download failed on first start
