# AGENTS.md

## Summary

This is the most reusable single-model inference scaffold in the repository. It is the best reference when you need to run one HubAI / Model Zoo model with one image-like input and one output stream, without building a task-specific multi-stage pipeline first.

## Use This Example When

- You need a simple starting point for running one model from the Luxonis Model Zoo.
- You want to switch between camera input and a media file with minimal code changes.
- You need a baseline for object detection, segmentation-like array outputs, or similar single-head models.
- You want a reference that already supports both peripheral mode and RVC4 standalone packaging.

## Do Not Use This Example When

- You need a multi-stage pipeline such as detect-then-crop-then-classify.
- You need a multi-input or multi-head model with custom wiring.
- You need stereo depth, point clouds, ROS topics, or a custom frontend.
- You need custom host-side decoding or task-specific postprocessing logic.

## Quick Facts

- `Category:` `neural-networks/generic-example`
- `Shape:` `script+standalone`
- `Primary task:` generic single-model inference
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` RVC2 peripheral, RVC4 peripheral, RVC4 standalone when the selected model supports the target platform
- `Requires:` a Luxonis device; selected model must exist for the target platform; media input is optional
- `Input:` camera input by default, or media file through `--media_path`
- `Output:` video passthrough plus parsed model output in the Visualizer
- `Models:` default is `luxonis/yolov6-nano:r2-coco-512x288`; arbitrary HubAI model slug supported when compatible
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [main.py](main.py): pipeline construction, model selection, and visualization topics
- [utils/arguments.py](utils/arguments.py): supported runtime knobs and default model
- [utils/input.py](utils/input.py): camera-versus-media input switching
- [oakapp.toml](oakapp.toml): standalone packaging path and default standalone entrypoint model
- [depthai_models/yolov6_nano_r2_coco.RVC2.yaml](depthai_models/yolov6_nano_r2_coco.RVC2.yaml): default RVC2 model descriptor
- [depthai_models/yolov6_nano_r2_coco.RVC4.yaml](depthai_models/yolov6_nano_r2_coco.RVC4.yaml): default RVC4 model descriptor

## Architecture

- The script creates one `dai.Device` and one `dai.RemoteConnection`.
- It chooses a platform-specific default model descriptor based on the connected device platform.
- If `--model` differs from the default YAML-backed model, it creates a new `dai.NNModelDescription` directly from the model slug.
- Input comes either from a `Camera` node or a `ReplayVideo` node created in [utils/input.py](utils/input.py).
- A `ParsingNeuralNetwork` node runs inference and returns parsed outputs.
- Visualization always publishes passthrough video and parsed detections/output.
- If `--overlay_mode` is enabled, array-like outputs are colorized and overlaid on the input frames before publishing.

## Data Flow

- `camera or media file -> input node -> ParsingNeuralNetwork -> parsed output`
- `ParsingNeuralNetwork.passthrough -> Video topic`
- `ParsingNeuralNetwork.out -> Detections topic`
- `ParsingNeuralNetwork.out -> ApplyColormap -> ImgFrameOverlay -> Video topic` when `--overlay_mode` is enabled

## Modification Guide

- `Safe to change:` model slug, API key handling, FPS limit, media path, Visualizer topic names
- `Requires care:` switching to models with incompatible input/output structure, changing overlay behavior, modifying standalone entrypoint defaults in [oakapp.toml](oakapp.toml)
- `Likely to break if changed blindly:` using multi-input or multi-head models, assuming every model returns detections, assuming overlay mode works for arbitrary parsed outputs

## Common Adaptations

- `To swap the model:` change `--model` first; only edit model YAMLs if you need a different default standalone baseline
- `To run on media instead of camera:` use `--media_path`; the input node will switch from `Camera` to `ReplayVideo`
- `To use a private model:` set `--api_key` or `DEPTHAI_HUB_API_KEY`
- `To reuse as a new example:` keep [main.py](main.py), [utils/input.py](utils/input.py), and [utils/arguments.py](utils/arguments.py), then replace the parser/output handling
- `To move between peripheral and standalone:` keep the same pipeline logic and update only [oakapp.toml](oakapp.toml) defaults if needed

## Constraints

- Only intended for one model with one image-like input and one parsed output stream.
- Standalone packaging exists, but model availability still depends on the target platform.
- `--overlay_mode` is only meaningful for outputs that can be rendered as image-like arrays.
- `ReplayVideo` frame type is platform-specific in [utils/input.py](utils/input.py); keep that logic intact when changing media handling.
- The standalone entrypoint in [oakapp.toml](oakapp.toml) hardcodes the default YOLOv6 model unless you edit it.

## Non-Obvious Repo Conventions

- Presence of [oakapp.toml](oakapp.toml) adds an RVC4 standalone path; it does not exclude peripheral usage.
- The default model is resolved through platform-specific YAML files first, then overridden by `--model` when requested.
- Parsed outputs are shown under a generic `Detections` topic even when the selected model is not an object detector.

## Related Examples

- [../object-detection/spatial-detections](../object-detection/spatial-detections/): use this when you need stereo spatial coordinates rather than a generic single-model scaffold
- [../object-detection/yolo-host-decoding](../object-detection/yolo-host-decoding/): use this when host-side YOLO decoding matters
- [../../tutorials/custom-models](../../tutorials/custom-models/): use this when the main task is custom model authoring or conversion rather than generic runtime wiring
- [../../apps/default-app](../../apps/default-app/): use this when you want a more app-shaped packaged baseline with fixed outputs

## Validation

- `Run:` `python3 main.py`
- `Alternative run:` `python3 main.py --model luxonis/mediapipe-selfie-segmentation:256x144 --overlay_mode`
- `Success looks like:` the Visualizer exposes `Video` and `Detections` topics and the pipeline runs until `q` is pressed
- `Common failure meaning:` model slug is unavailable for the target platform, private model auth is missing, or the chosen model does not fit the single-input/single-output assumptions
