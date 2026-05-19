# AGENTS.md

## Summary

This is the strongest standalone reference for interactive 3D object measurement from segmented point clouds. Use it when you need detections, object selection, pointcloud generation, and real-time dimension or volume estimation in one frontend/backend app.

## Use This Example When

- You need click-to-select measurement on top of RGB-aligned depth and pointclouds.
- You want a reference for open-vocabulary class control feeding a segmented measurement pipeline.
- You need both object-oriented bounding box and ground-plane height-grid measurement methods.
- You want a custom frontend with stream, pointcloud, selection, and measurement controls.

## Do Not Use This Example When

- You only need point-to-point distance measurement.
- You need a lightweight pointcloud example without segmentation and measurement logic.
- You need host/peripheral support rather than standalone-only RVC4 packaging.
- You need a mature image-prompt workflow; the current backend only supports class text updates.

## Quick Facts

- `Category:` `apps/object-volume-measurement-3d`
- `Shape:` `frontend`
- `Primary task:` interactive 3D dimensions and volume estimation from segmented point clouds
- `Entrypoint:` [backend/src/main.py](backend/src/main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` [frontend/src/App.tsx](frontend/src/App.tsx)
- `Runs on:` RVC4 standalone only
- `Requires:` RVC4 device with RGB, stereo, and IMU; static frontend build; bundled YOLOE model
- `Input:` RGB camera, stereo depth, IMU, frontend object clicks, class labels, confidence threshold, and measurement-method selection
- `Output:` `Video`, `Detections`, `Pointclouds`, `Measurement Overlay`, and `Plane Status`
- `Models:` [yoloe_v8_l.RVC4.yaml](backend/src/depthai_models/yoloe_v8_l.RVC4.yaml)
- `Visualizer / UI:` custom static frontend

## Read First

- [backend/src/main.py](backend/src/main.py): full pipeline, service registration, text-embedding updates, and measurement wiring
- [backend/src/utils/annotation_node.py](backend/src/utils/annotation_node.py): selection, segmentation, and overlay logic
- [backend/src/utils/measurement_node.py](backend/src/utils/measurement_node.py): measurement backend
- [backend/src/utils/PointCloudMeasurement.py](backend/src/utils/PointCloudMeasurement.py): pointcloud measurement helpers
- [backend/src/utils/helper_functions.py](backend/src/utils/helper_functions.py): text embeddings and intrinsics helpers
- [backend/src/utils/arguments.py](backend/src/utils/arguments.py): CLI arguments
- [frontend/src/App.tsx](frontend/src/App.tsx): combined stream and control layout
- [frontend/src/ClickOverlay.tsx](frontend/src/ClickOverlay.tsx): click-to-select behavior
- [frontend/src/ClassSelector.tsx](frontend/src/ClassSelector.tsx): class updates
- [frontend/src/MeasurementMethodSelector.tsx](frontend/src/MeasurementMethodSelector.tsx): OBB versus height-grid selection
- [oakapp.toml](oakapp.toml): static frontend build and Python 3.11 standalone base image

## Architecture

- RGB from `CAM_A` is resized and aligned with stereo depth from `CAM_B` and `CAM_C`.
- A YOLOE parsing NN consumes the RGB input and a text-embedding tensor input for class control.
- Detection filtering keeps only the currently active class labels.
- The annotation node handles segmentation, selection, and display overlays.
- An `RGBD` node creates pointcloud output for the segmented region.
- The measurement node estimates dimensions and volume, either by oriented bounding box or height-grid over a captured support plane.
- The frontend controls selection, classes, threshold, and measurement method through services.

## Data Flow

- `RGB + text embeddings -> ParsingNeuralNetwork -> filtered detections`
- `RGB + aligned depth + detections -> annotation node -> Detections`
- `segmented RGB + segmented depth -> RGBD -> Pointclouds`
- `Pointclouds + selection + IMU -> measurement node -> Measurement Overlay + Plane Status`

## Modification Guide

- `Safe to change:` initial classes, confidence threshold, frontend labels, measurement mode defaults, topic names
- `Requires care:` text-embedding updates, selection reset behavior, stereo alignment, plane-capture logic, intrinsics assumptions
- `Likely to break if changed blindly:` measurement method switching, pointcloud selection pipeline, or the label-encoding contract between backend and frontend

## Common Adaptations

- `To change the default classes:` edit `CLASS_NAMES` in [backend/src/main.py](backend/src/main.py)
- `To change confidence behavior:` edit the parser threshold and [frontend/src/ConfidenceSlider.tsx](frontend/src/ConfidenceSlider.tsx)
- `To reuse the pointcloud measurement backend:` keep [backend/src/utils/measurement_node.py](backend/src/utils/measurement_node.py) and feed it another segmented pointcloud source
- `To study a lighter RGBD reference:` compare against [depth-measurement/3d-measurement/rgbd-pointcloud](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/3d-measurement/rgbd-pointcloud)

## Constraints

- This example is intentionally RVC4 standalone only.
- The backend defaults to `8` FPS when no limit is provided.
- Height-grid measurement depends on a valid support-plane capture and IMU-assisted plane validation.
- [frontend/src/ImageUploader.tsx](frontend/src/ImageUploader.tsx) exists, but the backend does not register an `Image Upload Service`, so class updates are text-driven in the current implementation.
- [backend/src/utils/arguments.py](backend/src/utils/arguments.py) parses `--ip` and `--port`, but the current backend runtime does not use those values.

## Non-Obvious Repo Conventions

- Class changes are pushed into the NN through a `texts` input queue, not by rebuilding the model.
- Changing measurement method resets cached measurements and can trigger plane recapture.
- The frontend defaults to the `Video` and `Pointclouds` topics; measurement overlays are separate image topics emitted by the backend.

## Related Examples

- [apps/p2p-measurement](https://github.com/luxonis/oak-examples/tree/main/apps/p2p-measurement): use this when you only need two-point distance measurement
- [depth-measurement/3d-measurement/rgbd-pointcloud](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/3d-measurement/rgbd-pointcloud): use this when you need a cleaner RGBD pointcloud reference
- [apps/data-collection](https://github.com/luxonis/oak-examples/tree/main/apps/data-collection): use this when the main frontend pattern is interactive class control rather than 3D measurement
- [depth-measurement/calc-spatial-on-host](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/calc-spatial-on-host): use this when host-side spatial measurement is enough

## Validation

- `Run:` `oakctl app run .`
- `Success looks like:` the frontend shows the stream and pointclouds, clicking an object selects it, and measurements appear with the chosen method
- `Common failure meaning:` the device lacks the required stereo or IMU capabilities, the RVC4-only model/runtime assumptions were violated, or frontend code expected services that the backend does not expose
