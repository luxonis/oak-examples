# AGENTS.md

## Summary

Reusable single-model inference scaffold. It runs one Model Zoo model with one image-like input and one parsed output stream, using either camera input or a replayed media file.

## Use This Example When

- You need a simple starting point for one Model Zoo model.
- You want to switch between camera input and media-file input with minimal code changes.
- You need a baseline for object detection or array-like single-output models.
- You want a compact example that already has default RVC2/RVC4 model descriptors.

## Do Not Use This Example When

- You need multi-stage inference such as detect-then-crop-then-classify.
- You need multi-input, multi-head, host-decoded, or task-specific postprocessing logic.
- You need stereo depth, point clouds, ROS, C++, a custom frontend, or multi-device logic.

## Quick Facts

- `Entrypoint:` [main.py](main.py)
- `Input helper:` [utils/input.py](utils/input.py)
- `CLI options:` [utils/arguments.py](utils/arguments.py)
- `Default RVC2 model:` [depthai_models/yolov6_nano_r2_coco.RVC2.yaml](depthai_models/yolov6_nano_r2_coco.RVC2.yaml)
- `Default RVC4 model:` [depthai_models/yolov6_nano_r2_coco.RVC4.yaml](depthai_models/yolov6_nano_r2_coco.RVC4.yaml)
- `Standalone config:` [oakapp.toml](oakapp.toml)
- `Default model slug:` `luxonis/yolov6-nano:r2-coco-512x288`
- `Input:` camera by default, or media file via `--media_path`
- `Output:` `Video` passthrough plus parsed output on `Detections`

## Read First

- [main.py](main.py): model selection, pipeline construction, parser node, and Visualizer topics
- [utils/input.py](utils/input.py): camera versus `ReplayVideo` input selection and platform-specific frame type
- [utils/arguments.py](utils/arguments.py): model slug, FPS limit, media path, API key, and overlay options
- [oakapp.toml](oakapp.toml): standalone entrypoint and packaged defaults

## Architecture

- [main.py](main.py) connects to a device, reads the platform string, and chooses `yolov6_nano_r2_coco.<platform>.yaml` as the default descriptor.
- If `--model` differs from the YAML-backed default, [main.py](main.py) creates `dai.NNModelDescription(args.model, platform=platform)` instead.
- [utils/input.py](utils/input.py) returns either a camera node or a `ReplayVideo` node.
- `ParsingNeuralNetwork` runs the model and emits parsed output.
- `Video` shows `ParsingNeuralNetwork.passthrough` unless `--overlay_mode` is enabled.
- `Detections` always receives `ParsingNeuralNetwork.out`, even when the selected model is not an object detector.
- `--overlay_mode` colorizes `ParsingNeuralNetwork.out` and overlays it on passthrough frames.

## Data Flow

- `camera or media file -> ParsingNeuralNetwork -> parsed output`
- `ParsingNeuralNetwork.passthrough -> Video`
- `ParsingNeuralNetwork.out -> Detections`
- `ParsingNeuralNetwork.out -> ApplyColormap -> ImgFrameOverlay -> Video` when `--overlay_mode` is enabled

## Modification Guide

- `Safe to change:` model slug, FPS limit, media path, private API key handling, Visualizer topic names
- `Requires care:` model input/output compatibility, overlay assumptions, platform-specific media frame types, standalone defaults in [oakapp.toml](oakapp.toml)
- `Likely to break if changed blindly:` using multi-input or multi-head models, assuming every parsed output is a detection, enabling overlay for non-image-like outputs

## Common Adaptations

- `Swap the model:` pass `--model` first; edit YAMLs only if changing the default packaged baseline.
- `Run on media:` pass `--media_path`; [utils/input.py](utils/input.py) switches from `Camera` to `ReplayVideo`.
- `Use a private model:` set `--api_key` or `DEPTHAI_HUB_API_KEY`.
- `Create a task-specific example:` keep [main.py](main.py), [utils/input.py](utils/input.py), and [utils/arguments.py](utils/arguments.py), then replace parser/output handling as needed.

## Constraints

- Intended for one model, one image-like input, and one parsed output stream.
- Model availability still depends on the selected platform.
- `--overlay_mode` only makes sense for outputs that can be rendered as image-like arrays.
- `ReplayVideo` frame type is platform-specific; keep [utils/input.py](utils/input.py) aligned with supported platforms.
- [oakapp.toml](oakapp.toml) hardcodes the default YOLOv6 model unless changed.

## Related Examples

- [../object-detection/spatial-detections](../object-detection/spatial-detections/): detections with stereo spatial coordinates
- [../object-detection/yolo-host-decoding](../object-detection/yolo-host-decoding/): YOLO raw output decoded on the host
- [../../tutorials/custom-models](../../tutorials/custom-models/): custom model authoring or conversion
- [../../apps/default-app](../../apps/default-app/): more app-shaped packaged baseline with fixed outputs

## Validation

- `Run:` `python3 main.py`
- `Alternative run:` `python3 main.py --model luxonis/mediapipe-selfie-segmentation:256x144 --overlay_mode`
- `Success looks like:` Visualizer exposes `Video` and `Detections`, and the pipeline runs until `q` is pressed
- `Common failure meaning:` model slug unavailable for platform, private model auth missing, or selected model violates the single-input/single-output assumptions
