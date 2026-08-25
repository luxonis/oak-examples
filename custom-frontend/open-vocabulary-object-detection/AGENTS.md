# AGENTS.md

## Summary

This is the strongest custom-frontend reference in the repository for open-vocabulary detection with runtime prompt updates. Use it when you need a standalone frontend/backend app that supports text prompts, image prompts, bbox-derived visual prompts, model-specific prompt encoding, and backend-driven state restore.

## Use This Example When

- You need a richer standalone frontend/backend pattern than [custom-frontend/raw-stream](https://github.com/luxonis/oak-examples/tree/main/custom-frontend/raw-stream).
- You want open-vocabulary detection where classes can be changed at runtime from the UI.
- You need image-prompt and bbox-prompt flows in addition to text prompts.
- You want a reference for backend-owned prompt state that is restored into the frontend on connect.

## Do Not Use This Example When

- You need a host/peripheral custom frontend example.
- You need a minimal service demo without prompt encoders or model switching.
- You need a generic single-model baseline with no custom UI.
- You need a finished multi-app pattern for snapping, tracking, or measurement instead of prompt-driven detection.

## Quick Facts

- `Category:` `custom-frontend/open-vocabulary-object-detection`
- `Shape:` `frontend`
- `Primary task:` open-vocabulary object detection with runtime text/image/bbox prompting
- `Entrypoint:` [backend/src/main.py](backend/src/main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` [frontend/src/App.tsx](frontend/src/App.tsx)
- `Runs on:` RVC4 standalone only
- `Requires:` RVC4 device; static frontend build; prompt encoder dependencies from [backend/requirements.txt](backend/requirements.txt), including `depthai-nodes==0.6.1`; the ONNX Runtime OakApp base image
- `Input:` live camera by default, or media file via `--media_path`; text classes, uploaded images, or drawn bounding boxes from the frontend
- `Output:` `Video` and `Detections`
- `Models:` YOLOE and YOLO-World model descriptors under [backend/src/depthai_models/](backend/src/depthai_models/)
- `Visualizer / UI:` custom static frontend served through the oakapp container stack

## Read First

- [backend/src/main.py](backend/src/main.py): overall backend pipeline, service registration, and model-specific visualization branch
- [backend/src/config/arguments.py](backend/src/config/arguments.py): actual CLI arguments supported by the backend
- [backend/src/config/system_configuration.py](backend/src/config/system_configuration.py): model selection and YAML-backed configuration
- [backend/src/config/yaml_configs/config.yaml](backend/src/config/yaml_configs/config.yaml): default model, precision, NN backend, and video defaults
- [backend/src/config/yaml_configs/prompts_yoloe.yaml](backend/src/config/yaml_configs/prompts_yoloe.yaml): YOLOE prompt encoder config and limits
- [backend/src/config/yaml_configs/prompts_yolo_world.yaml](backend/src/config/yaml_configs/prompts_yolo_world.yaml): YOLO-World prompt encoder config and limits
- [backend/src/nn/nn_detection_node.py](backend/src/nn/nn_detection_node.py): high-level NN block wiring
- [backend/src/nn/nn_detection_controller.py](backend/src/nn/nn_detection_controller.py): runtime prompt, label, and threshold state management
- [backend/src/prompting/fe_services.py](backend/src/prompting/fe_services.py): service payload handling for text, image, bbox, rename, and delete operations
- [backend/src/visualization/segmentation_overlay_node.py](backend/src/visualization/segmentation_overlay_node.py): YOLOE-specific segmentation overlay path
- [frontend/src/App.tsx](frontend/src/App.tsx): UI composition, bbox drawing, and prompt state restore
- [frontend/src/ClassSelector.tsx](frontend/src/ClassSelector.tsx): text-class updates
- [frontend/src/ImageUploader.tsx](frontend/src/ImageUploader.tsx): image upload and bbox-drawing entrypoints
- [frontend/src/ConfidenceSlider.tsx](frontend/src/ConfidenceSlider.tsx): threshold control
- [frontend/src/main.tsx](frontend/src/main.tsx): `DepthAIContext`, notifications, and router setup
- [oakapp.toml](oakapp.toml): static frontend build, backend packaging, and bundled model path

## Architecture

- The backend creates a `dai.Device` and a `dai.RemoteConnection` with `serveFrontend=False`.
- `CameraSourceNode` provides the source frames.
- `NNDetectionNode` wraps the prompt-driven detector, filter, label mapper, and runtime controller.
- `FrameCacheNode` stores the latest frame so bbox/image prompt services can derive embeddings from current video content.
- `PromptingFEServices` exposes text prompt updates, confidence changes, image uploads, bbox prompts, image-prompt rename, and image-prompt delete.
- `GetCurrentParamsService` exports the current text classes, image prompt labels, and confidence threshold back to the frontend.
- When the configured model is `yoloe`, [backend/src/visualization/segmentation_overlay_node.py](backend/src/visualization/segmentation_overlay_node.py) publishes an encoded segmentation overlay as `Video`.
- When the configured model is `yolo-world`, the backend publishes the encoded camera stream as `Video` and sends detections separately.

## Data Flow

- `camera or media -> CameraSourceNode -> NNDetectionNode -> Detections`
- `YOLOE detections + frames -> SegmentationOverlayNode -> Video` when model is `yoloe`
- `camera encoded stream -> Video` when model is `yolo-world`
- `frontend text/image/bbox services -> NNDetectionController -> prompt tensors + label/filter updates`
- `backend NN state -> Get Current Params Service -> frontend state restore`

## Modification Guide

- `Safe to change:` default classes, default model, frontend layout, notification behavior, topic names, prompt-label UX
- `Requires care:` model-specific prompt tensor offsets, bbox coordinate mapping, label-offset handling, state restore payload shape, and YOLOE versus YOLO-World visualization differences
- `Likely to break if changed blindly:` service naming across backend and frontend, switching between text and image prompts, or label filtering when prompt offsets change

## Common Adaptations

- `To change the default model:` edit [backend/src/config/yaml_configs/config.yaml](backend/src/config/yaml_configs/config.yaml)
- `To change prompt limits:` edit `max_num_classes` and `max_image_prompts` in the prompt YAMLs under [backend/src/config/yaml_configs/](backend/src/config/yaml_configs/)
- `To add another prompt source:` extend [backend/src/prompting/fe_services.py](backend/src/prompting/fe_services.py) and add a matching control in [frontend/src/App.tsx](frontend/src/App.tsx)
- `To reuse just the open-vocabulary backend:` keep [backend/src/nn/](backend/src/nn/) and [backend/src/prompting/](backend/src/prompting/), then replace the frontend with another service client
- `To step down to a minimal custom frontend baseline:` compare against [custom-frontend/raw-stream](https://github.com/luxonis/oak-examples/tree/main/custom-frontend/raw-stream)

## Constraints

- This example is intentionally RVC4 standalone only.
- Prompt encoders use `depthai_nodes.runtime.onnx_qnn_session` on the ONNX Runtime base image; the app must retain the NPU devices and `/opt/luxonis/npu-runtime` mount declared in [oakapp.toml](oakapp.toml).
- The backend only supports the CLI arguments defined in [backend/src/config/arguments.py](backend/src/config/arguments.py): `--fps_limit`, `--media_path`, `--model`, and `--semantic_seg`.
- The current backend does not parse `--precision`, `--ip`, or `--port`.
- `config.yaml` currently fixes precision to `fp16`, and [backend/src/config/system_configuration.py](backend/src/config/system_configuration.py) only maps `yoloe` to an `fp16` YAML while `yolo-world` supports `fp16` and `int8`.
- `max_image_prompts` is `5` in both prompt YAMLs, and the frontend assumes the same limit.
- `--semantic_seg` only affects the YOLOE visualization branch.

## Non-Obvious Repo Conventions

- Updating text classes clears accumulated image prompts on the backend by design.
- When the last image prompt is deleted, the backend reverts automatically to the last text-class set.
- Bbox prompting is model-specific: YOLO-World crops the bbox region itself, while YOLOE keeps the full frame and applies a mask.
- The frontend restores prompt state by fetching `Get Current Params Service` rather than owning the source of truth locally.

## Related Examples

- [custom-frontend/raw-stream](https://github.com/luxonis/oak-examples/tree/main/custom-frontend/raw-stream): use this when you need the smallest frontend/backend baseline with one service and one stream
- [apps/data-collection](https://github.com/luxonis/oak-examples/tree/main/apps/data-collection): use this when you want another prompt-driven standalone app with more backend state and snap logic
- [neural-networks/generic-example](https://github.com/luxonis/oak-examples/tree/main/neural-networks/generic-example): use this when you want a generic single-model baseline with no custom UI
- [apps/object-volume-measurement-3d](https://github.com/luxonis/oak-examples/tree/main/apps/object-volume-measurement-3d): use this when you want another click-driven custom frontend with backend services

## Validation

- `Run:` `oakctl app run .`
- `Success looks like:` the frontend loads, current params are restored from the backend, text or image prompts change the active detections, and bbox drawing produces a new image prompt label
- `Common failure meaning:` frontend/backend service contracts drifted, the static frontend build failed, model assets or prompt encoders are unavailable, or the README instructions were followed instead of the actual current CLI/config code
