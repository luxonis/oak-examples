# AGENTS.md

## Summary

This is the best standalone reference for open-vocabulary detection plus configurable automatic snap collection. Use it when you need a frontend/backend app where the UI changes classes, thresholds, prompt sources, and snapping conditions while the backend remains authoritative over capture logic.

## Use This Example When

- You need open-vocabulary detection with text prompts, image prompts, and bbox-based prompting.
- You want to auto-capture frames and metadata under configurable snap conditions.
- You need a custom frontend that restores backend state on connect.
- You want a stronger standalone app reference than the generic single-model scaffold.

## Do Not Use This Example When

- You only need a plain single-model inference example without UI.
- You need host/peripheral support on RVC2 or RVC4 as the main path.
- You need 3D measurement or pointcloud workflows.
- You need similarity tracking rather than open-vocabulary prompting.

## Quick Facts

- `Category:` `apps/data-collection`
- `Shape:` `frontend`
- `Primary task:` open-vocabulary snap collection with configurable conditions
- `Entrypoint:` [backend/src/main.py](backend/src/main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` [frontend/src/App.tsx](frontend/src/App.tsx)
- `Runs on:` RVC4 standalone only
- `Requires:` RVC4 device; static frontend build; bundled YOLOE model; `depthai-nodes==0.6.1`; the ONNX Runtime OakApp base image; backend YAML configs in [backend/src/config/yaml_configs/](backend/src/config/yaml_configs/)
- `Input:` live RGB camera by default, or media input via `--media_path`; text prompt, image prompt, or bbox prompt from the frontend
- `Output:` encoded `Video`, `Annotations`, and saved snaps with metadata controlled by backend snapping logic
- `Models:` [yoloe_v8_l_fp16.RVC4.yaml](backend/src/depthai_models/yoloe_v8_l_fp16.RVC4.yaml)
- `Visualizer / UI:` custom static frontend served through the oakapp container stack

## Read First

- [backend/src/main.py](backend/src/main.py): end-to-end pipeline and frontend service registration
- [backend/src/config/system_configuration.py](backend/src/config/system_configuration.py): how CLI args and YAMLs become runtime config
- [backend/src/config/yaml_configs/config.yaml](backend/src/config/yaml_configs/config.yaml): baseline video, NN, and tracker defaults
- [backend/src/config/yaml_configs/conditions.yaml](backend/src/config/yaml_configs/conditions.yaml): snap-condition defaults
- [backend/src/config/yaml_configs/prompts_config.yaml](backend/src/config/yaml_configs/prompts_config.yaml): prompt-related defaults
- [backend/src/nn/nn_detection_node.py](backend/src/nn/nn_detection_node.py): backend detection node
- [backend/src/snapping/snapping_node.py](backend/src/snapping/snapping_node.py): snap-condition handling
- [backend/src/prompting/fe_services.py](backend/src/prompting/fe_services.py): frontend prompt service handlers
- [frontend/src/App.tsx](frontend/src/App.tsx): stream, bbox prompt drawing, and config restore flow
- [frontend/src/utils/classes/ClassSelector.tsx](frontend/src/utils/classes/ClassSelector.tsx): text-class control
- [frontend/src/utils/classes/ImageUploader.tsx](frontend/src/utils/classes/ImageUploader.tsx): visual prompt upload
- [frontend/src/utils/conditions/SnapConditionsPanel.tsx](frontend/src/utils/conditions/SnapConditionsPanel.tsx): snap-condition UI
- [oakapp.toml](oakapp.toml): static frontend build and standalone packaging

## Architecture

- The backend builds config from CLI args plus YAML files.
- `CameraSourceNode` provides frames.
- `NNDetectionNode` runs the open-vocabulary detector.
- A tracker is built from [backend/src/tracking/tracker_builder.py](backend/src/tracking/tracker_builder.py).
- `SnappingNode` decides when snaps should be emitted based on detections and tracklets.
- `FrameCacheNode` stores the latest frame for image-prompt workflows.
- The backend registers services for class updates, threshold updates, image upload, bbox prompting, snap-condition updates, and config export.

## Data Flow

- `camera or media -> CameraSourceNode -> NNDetectionNode -> Annotations`
- `NN detections + tracker output -> SnappingNode -> snap events`
- `latest frame cache + frontend prompt services -> detector prompt updates`
- `backend state -> Get App Config Service -> frontend state restore`

## Modification Guide

- `Safe to change:` default classes, thresholds, snap-condition defaults, frontend layout, config YAML values
- `Requires care:` service payload contracts, state export format, tracker-to-snapping coupling, prompt encoder wiring
- `Likely to break if changed blindly:` frontend restore behavior, bbox prompt coordinate handling, or condition naming shared between backend and frontend

## Common Adaptations

- `To change default runtime behavior:` start in [backend/src/config/yaml_configs/](backend/src/config/yaml_configs/)
- `To add a new prompt source:` extend [backend/src/prompting/](backend/src/prompting/) and wire a matching control in [frontend/src/App.tsx](frontend/src/App.tsx)
- `To add a new snap condition:` extend [backend/src/snapping/conditions.py](backend/src/snapping/conditions.py) and [frontend/src/utils/conditions/](frontend/src/utils/conditions/)
- `To reuse the open-vocabulary detector without snaps:` keep the NN and prompting pieces and remove [backend/src/snapping/snapping_node.py](backend/src/snapping/snapping_node.py)

## Constraints

- This example is intentionally RVC4 standalone only.
- Prompt encoders use `depthai_nodes.runtime.onnx_qnn_session` on the ONNX Runtime base image; the app must retain the NPU devices and `/opt/luxonis/npu-runtime` mount declared in [oakapp.toml](oakapp.toml).
- The backend uses `serveFrontend=False`, so the app depends on the static frontend build declared in [oakapp.toml](oakapp.toml).
- Runtime behavior is split across CLI args and YAML config files, so changing only one side may not do what you expect.
- The frontend expects the backend to be the source of truth and rehydrates local UI state from `Get App Config Service`.

## Non-Obvious Repo Conventions

- The config service wraps the exported state under a `data` key, and the frontend parses that shape explicitly.
- Prompt updates are service-driven, not topic-driven.
- [oakapp.toml](oakapp.toml) bundles both the backend Python environment and the built frontend assets, so this is a stronger standalone reference than the default Visualizer apps.

## Related Examples

- [apps/dino-tracking](https://github.com/luxonis/oak-examples/tree/main/apps/dino-tracking): use this when you need interactive tracking rather than open-vocabulary snapping
- [apps/object-volume-measurement-3d](https://github.com/luxonis/oak-examples/tree/main/apps/object-volume-measurement-3d): use this when you need object clicks and a richer 3D measurement backend
- [custom-frontend/open-vocabulary-object-detection](https://github.com/luxonis/oak-examples/tree/main/custom-frontend/open-vocabulary-object-detection): use this when you want another open-vocabulary frontend/backend pattern
- [neural-networks/generic-example](https://github.com/luxonis/oak-examples/tree/main/neural-networks/generic-example): use this when you want the lighter single-model baseline

## Validation

- `Run:` `oakctl app run .`
- `Success looks like:` the frontend shows live video, class and threshold updates work, bbox/image prompts reach the backend, and snap-condition state restores correctly after reconnect
- `Common failure meaning:` the static frontend was not built, the RVC4-only model/runtime assumptions were violated, or frontend/backend service contracts drifted
