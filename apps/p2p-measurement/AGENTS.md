# AGENTS.md

## Summary

This is the reference app for interactive two-point 3D distance measurement on RVC2 (peripheral) and RVC4 (peripheral and standalone). Use it when you need click-based point selection, aligned RGB-depth visualization, and host-side tracking or remeasurement of selected points without the heavier segmentation and pointcloud logic from the 3D volume app.

## Use This Example When

- You need Euclidean distance between two image points using aligned depth.
- You want click-to-select measurement with a custom frontend.
- You need a host-node example that tracks selected points across frames.
- You want a simpler measurement app than the full 3D object-volume workflow.

## Do Not Use This Example When

- You need segmented pointclouds and object volume.
- You need a generic depth baseline with no frontend.
- You need RVC2 standalone packaging (RVC2 supports peripheral mode only).
- You need a polished ROS measurement workflow.

## Quick Facts

- `Category:` `apps/p2p-measurement`
- `Shape:` `frontend`
- `Primary task:` interactive two-point 3D distance measurement
- `Entrypoint:` [backend/src/main.py](backend/src/main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` [frontend/src/App.tsx](frontend/src/App.tsx)
- `Runs on:` RVC2 (peripheral), RVC4 (standalone and peripheral)
- `Requires:` RVC2 or RVC4 device with RGB and stereo; calibration on device; static frontend build
- `Input:` RGB camera, unified depth, and frontend point clicks
- `Output:` `Video`, `Depth`, `Point Annotations`, and service-based distance/tracking state
- `Models:` none
- `Visualizer / UI:` custom static frontend (served by oakapp in standalone mode, or by [backend/src/utils/frontend_server.py](backend/src/utils/frontend_server.py) in peripheral mode)

## Read First

- [backend/src/main.py](backend/src/main.py): pipeline, services, topic publication, and peripheral frontend server lifecycle
- [backend/src/utils/frontend_server.py](backend/src/utils/frontend_server.py): static bundle HTTP/HTTPS server for peripheral mode (disabled in standalone mode)
- [backend/src/utils/point_tracker.py](backend/src/utils/point_tracker.py): point selection, tracking modes, annotations, and distance state
- [backend/src/utils/distance_calculator.py](backend/src/utils/distance_calculator.py): depth-to-distance logic
- [backend/src/utils/arguments.py](backend/src/utils/arguments.py): CLI arguments
- [frontend/src/App.tsx](frontend/src/App.tsx): polling, click handling, tracking toggle, and instructions
- [frontend/src/ClickOverlay.tsx](frontend/src/ClickOverlay.tsx): click-to-point mapping
- [frontend/src/DistanceDisplay.tsx](frontend/src/DistanceDisplay.tsx): measurement readout
- [oakapp.toml](oakapp.toml): static frontend build and Python 3.11 standalone base image

## Architecture

- `CAM_A` provides RGB frames.
- `Depth` owns depth-source selection and stereo camera setup when stereo is selected.
- `Depth.setAlignTo(...)` aligns depth to RGB.
- A colorized depth stream is published for viewing.
- The custom [backend/src/utils/point_tracker.py](backend/src/utils/point_tracker.py) host node tracks selected points, computes 3D distance using the current aligned depth frame’s native inverse intrinsic matrix, and emits overlay annotations.
- The frontend interacts with backend services for point selection, clearing, distance polling, and tracking-mode toggling.
- In peripheral mode, [backend/src/utils/frontend_server.py](backend/src/utils/frontend_server.py) serves the built static bundle from `frontend/dist` over HTTP (default port `8082`) or optional local HTTPS (`--https`).
- In standalone mode, [oakapp.toml](oakapp.toml) passes `--no-frontend` (and the runtime sets `OAKAPP_STATIC_FRONTEND_PORT`), so the Python HTTP server is skipped and `oakapp` serves `[static_frontend]` directly.

## Data Flow

- `RGB + Depth -> aligned depth`
- `aligned depth -> ApplyDepthColormap -> Depth`
- `RGB + aligned depth -> PointTracker host node -> Point Annotations`
- `frontend clicks -> Selection Service -> PointTracker state`
- `PointTracker state -> Get Distance Service / Get Tracking Status Service -> frontend display`

## Modification Guide

- `Safe to change:` frontend instructions, polling cadence, display units, annotation styling, default FPS
- `Requires care:` click-coordinate normalization, calibration handling, point-tracking modes, depth validity checks
- `Likely to break if changed blindly:` tracking-mode semantics, point reset behavior, or the mapping between displayed pixels and measurement pixels

## Common Adaptations

- `To disable tracking and make measurements static:` simplify [backend/src/utils/point_tracker.py](backend/src/utils/point_tracker.py) and remove the tracking services
- `To change measurement behavior:` start in [backend/src/utils/distance_calculator.py](backend/src/utils/distance_calculator.py)
- `To reuse only the click-selection frontend:` keep [frontend/src/ClickOverlay.tsx](frontend/src/ClickOverlay.tsx) and replace the backend services
- `To move to richer 3D measurement:` compare against [apps/object-volume-measurement-3d](https://github.com/luxonis/oak-examples/tree/main/apps/object-volume-measurement-3d)

## Constraints

- Standalone mode is RVC4 only; peripheral mode supports both RVC2 and RVC4.
- Peripheral mode requires building the static frontend bundle (`cd frontend && npm ci && npm run build`) before running [backend/src/main.py](backend/src/main.py).
- The backend defaults to `15` FPS when no limit is provided.
- Measurement quality depends on valid aligned depth for both points.
- The frontend polls `Get Distance Service` at a high rate, so service responsiveness matters.

## Non-Obvious Repo Conventions

- Clearing points is handled through `Selection Service` with `{clear: true}` as well as a separate `Clear Points Service`.
- The host tracker supports multiple modes internally: tracking, meter, and static.
- Spacebar and right-click reset are frontend conveniences layered on top of the same backend point-clearing behavior.
- Standalone mode excludes the Python static web server via both `--no-frontend` in [oakapp.toml](oakapp.toml) and `OAKAPP_STATIC_FRONTEND_PORT` detection in [backend/src/utils/frontend_server.py](backend/src/utils/frontend_server.py).

## Related Examples

- [apps/object-volume-measurement-3d](https://github.com/luxonis/oak-examples/tree/main/apps/object-volume-measurement-3d): use this when you need segmented object measurement instead of two-point distance
- [depth-measurement/calc-spatial-on-host](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/calc-spatial-on-host): use this when host-side spatial ROI measurement is enough
- [tutorials/camera-depth](https://github.com/luxonis/oak-examples/tree/main/tutorials/camera-depth): use this when you need a simpler depth baseline
- [depth-measurement/stereo-on-host](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/stereo-on-host): use this when the main goal is host-side stereo processing, not an interactive measurement UI

## Validation

- `Hardware check:` Measure a known distance at the image center and corners, then repeat with another output aspect ratio.
- `Run:` standalone: `oakctl app run .`; peripheral: `cd frontend && npm ci && npm run build && cd .. && python3 backend/src/main.py` (or add `--https` for local HTTPS)
- `Success looks like:` the frontend loads on `http://localhost:8082` (or `https://localhost:8082` with `--https`, or `https://<OAK4_IP>:9000/` in standalone), shows RGB or depth, two clicks create a measurement, and toggling tracking changes whether the selected points continue to move with the target
- `Common failure meaning:` missing `frontend/dist` build in peripheral mode, stereo alignment or calibration is missing, invalid depth prevents measurement, or frontend topic/service assumptions drifted from the backend
