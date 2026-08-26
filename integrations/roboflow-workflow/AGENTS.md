# AGENTS.md

## Summary

This is the strongest integration reference in the repository for running Roboflow Workflows against live DepthAI camera frames with a custom frontend. Use it when you need a standalone-only frontend/backend app where external inference owns the detections and the local backend owns stream delivery, workflow-output discovery, and frontend parameter updates.

## Use This Example When

- You need a custom frontend around Roboflow Workflow inference.
- You want runtime updates to Roboflow credentials, workflow identity, or workflow parameters from the UI.
- You need a reference for adapting arbitrary Roboflow workflow outputs into DepthAI topics.
- You want an app-shaped standalone example rather than a simple integration script.

## Do Not Use This Example When

- You need a peripheral-mode custom frontend example.
- You need dataset export rather than live workflow inference.
- You need a device-side NN baseline with repo-local models.

## Quick Facts

- `Category:` `integrations/roboflow-workflow`
- `Shape:` `frontend`
- `Primary task:` run Roboflow Workflow inference on live DepthAI frames and surface outputs in a custom frontend
- `Entrypoint:` [backend/src/main.py](backend/src/main.py)
- `Standalone path:` [backend-run.sh](backend-run.sh) and [oakapp.toml](oakapp.toml)
- `Frontend:` [frontend/src/App.tsx](frontend/src/App.tsx)
- `Runs on:` documented as RVC4 standalone only
- `Requires:` RVC4 device running Luxonis OS 1.40 or newer; valid Roboflow workflow config in [backend/src/config/yaml_configs/config.yaml](backend/src/config/yaml_configs/config.yaml); the `inference` package; and static frontend assets
- `Input:` live camera frames from the device plus optional parameter-update payloads from the frontend
- `Output:` `passthrough` plus any workflow-derived `*visualization*` or `*predictions*` topics that the schema exposes
- `Models:` external Roboflow Workflow models, not repo-local model YAMLs
- `Visualizer / UI:` custom frontend built on `@luxonis/depthai-viewer-common`

## Read First

- [README.md](README.md): workflow setup expectations and naming rules
- [backend/src/main.py](backend/src/main.py): startup order, service registration, and shutdown flow
- [backend/src/config/config.py](backend/src/config/config.py): config schema and load path
- [backend/src/config/yaml_configs/config.yaml](backend/src/config/yaml_configs/config.yaml): initial Roboflow and pipeline configuration
- [backend/src/core/depthai_pipeline.py](backend/src/core/depthai_pipeline.py): local camera pipeline and `VideoFrameProducer` factory
- [backend/src/core/frame_producer.py](backend/src/core/frame_producer.py): `VideoFrameProducer` implementation bridging the DepthAI output queue into `InferencePipeline`
- [backend/src/core/annotation_node.py](backend/src/core/annotation_node.py): workflow-output parsing and topic creation
- [backend/src/core/manager.py](backend/src/core/manager.py): runtime update service and rebuild logic
- [backend/src/core/roboflow_runner.py](backend/src/core/roboflow_runner.py): Roboflow `InferencePipeline` wrapper and workflow-output discovery via the Roboflow API
- [backend/src/core/visualizer_wrapper.py](backend/src/core/visualizer_wrapper.py): topic/service wrapper around `dai.RemoteConnection`
- [frontend/src/App.tsx](frontend/src/App.tsx): UI shell and stream layout
- [frontend/src/MessageInput.tsx](frontend/src/MessageInput.tsx): runtime parameter update form
- [oakapp.toml](oakapp.toml): backend service entrypoint and static frontend build path

## Architecture

- Backend startup loads [backend/src/config/yaml_configs/config.yaml](backend/src/config/yaml_configs/config.yaml) into a Pydantic config object.
- `RoboflowRunner` wraps `InferencePipeline.init_with_workflow(...)` and drives it with `start(use_main_thread=False)` / `terminate()` / `join()`.
- Before the live app starts, `fetch_workflow_output_names()` downloads the workflow definition through the Roboflow API (`get_workflow_specification`) to discover the output names.
- `DepthAIPipeline` creates a local camera pipeline, registers topics based on the discovered output names, and exposes `create_frame_producer()` - a `VideoFrameProducer` factory passed to `InferencePipeline` as `video_reference` (no `cv2.VideoCapture` patching).
- `AnnotationNode` classifies Roboflow outputs by name:
  - keys containing `visualization` become image topics
  - keys containing `predictions` become detection topics
  - everything else is ignored
- `RoboflowManager` registers the `Roboflow Parameter Update Service` and decides whether an update only restarts the Roboflow runner or fully rebuilds the DepthAI pipeline and topics.
- The frontend renders `Streams` and posts update payloads back to the backend service.

## Data Flow

- `DepthAI camera -> DepthAIPipeline queue -> DepthAIFrameProducer -> Roboflow InferencePipeline`
- `Roboflow prediction callback -> AnnotationNode.on_prediction() -> passthrough/image/detection topics`
- `topics -> VisualizerWrapper -> frontend Streams view`
- `frontend form -> Roboflow Parameter Update Service -> RoboflowManager -> runner restart or full pipeline rebuild`

## Modification Guide

- `Safe to change:` frontend copy/layout, service success/error UX, initial config values, topic labels exposed from the backend
- `Requires care:` workflow-output discovery, the `VideoFrameProducer` lifecycle (`grab()` timeout vs. runner stop order), naming-based output parsing, and the restart-versus-rebuild distinction in [backend/src/core/manager.py](backend/src/core/manager.py)
- `Likely to break if changed blindly:` workflow output naming, service payload shape between [frontend/src/MessageInput.tsx](frontend/src/MessageInput.tsx) and [backend/src/core/manager.py](backend/src/core/manager.py), or the static frontend build path in [oakapp.toml](oakapp.toml)

## Common Adaptations

- `To support additional workflow output types:` extend [backend/src/core/annotation_node.py](backend/src/core/annotation_node.py)
- `To make pipeline settings updateable from the UI:` extend [frontend/src/MessageInput.tsx](frontend/src/MessageInput.tsx), [backend/src/core/manager.py](backend/src/core/manager.py), and the config model in [backend/src/config/config.py](backend/src/config/config.py)
- `To reuse only the backend workflow bridge:` keep [backend/src/core/](backend/src/core/) and replace the frontend with another service client
- `To step down to a smaller frontend/backend baseline:` compare with [custom-frontend/raw-stream](https://github.com/luxonis/oak-examples/tree/main/custom-frontend/raw-stream)

## Constraints

- This example is documented and packaged as RVC4 standalone only.
- Workflow outputs whose names contain neither `visualization` nor `predictions` are ignored by the backend.
- The current frontend/backend update path only supports `api_key`, `workspace_name`, `workflow_id`, and `workflow_parameters`; it does not update `device`, `output_size`, or `fps`.
- Luxonis OS 1.40 or newer is required for the device NPU runtime.

## Non-Obvious Repo Conventions

- Frames flow into Roboflow through the official `VideoFrameProducer` interface (`video_reference` accepts a producer factory), so no global state is patched.
- The backend exports `USE_INFERENCE_MODELS=False` (see [backend-run.sh](backend-run.sh)) to run models through the classic ONNX Runtime path instead of the torch-based `inference-models` backend, which is markedly slower on the device's ARM CPU.
- `core/qnn_patch.py` routes the ONNX Runtime path through the QNN session helper.
- `dai.ImgDetections.detections` returns a copy; the parsed detection list must be assigned back to the property, appending to it is silently ignored.
- If only workflow parameters change, [backend/src/core/manager.py](backend/src/core/manager.py) restarts just the Roboflow runner; if the workflow identity or credentials change, it rebuilds the full DepthAI topic surface.
- `passthrough` is always present as a local topic because [backend/src/core/annotation_node.py](backend/src/core/annotation_node.py) seeds `output_frames` with that key.
- The frontend’s service name must stay aligned with the backend registration string `Roboflow Parameter Update Service`.

## Related Examples

- [integrations/roboflow-dataset](https://github.com/luxonis/oak-examples/tree/main/integrations/roboflow-dataset): use this when Roboflow is the dataset sink instead of the inference engine
- [custom-frontend/raw-stream](https://github.com/luxonis/oak-examples/tree/main/custom-frontend/raw-stream): use this when you need a much smaller frontend/backend baseline
- [custom-frontend/open-vocabulary-object-detection](https://github.com/luxonis/oak-examples/tree/main/custom-frontend/open-vocabulary-object-detection): use this when you need another standalone custom frontend with richer backend-owned inference state
- [apps/default-app](https://github.com/luxonis/oak-examples/tree/main/apps/default-app): use this when you want a packaged app baseline with repo-local inference instead of external workflows

## Validation

- `Run:` populate [backend/src/config/yaml_configs/config.yaml](backend/src/config/yaml_configs/config.yaml), then run `oakctl app run .`
- `Success looks like:` the frontend loads, `passthrough` plus recognized workflow outputs appear as streams/topics, and submitting the form updates Roboflow workflow settings without breaking the connection
- `Common failure meaning:` the initial Roboflow config is invalid, the workflow output names do not match the backend naming rules, the frontend/backend service contract drifted, or the current static frontend build path issues in [oakapp.toml](oakapp.toml) and [frontend/package.json](frontend/package.json) were not accounted for
