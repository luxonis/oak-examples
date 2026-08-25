# AGENTS.md

## Summary

This is the repository reference for open-vocabulary YOLO-World inference with static text prompts. Use it when you need prompt-conditioned detection without the heavier custom-frontend app layer.

## Use This Example When

- You need open-vocabulary object detection.
- You want text prompts supplied once at startup rather than a custom runtime UI.
- You need a multi-input detector example on RVC4.

## Do Not Use This Example When

- You need runtime prompt editing from a frontend.
- You need RVC2 support.
- You need a fixed closed-set detector.

## Quick Facts

- `Category:` `neural-networks/object-detection/yolo-world`
- `Shape:` `script+standalone`
- `Primary task:` open-vocabulary object detection with text embeddings
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` RVC4 peripheral and RVC4 standalone packaging
- `Requires:` YOLO-World model, text embeddings generated from class names, RVC4 `snpe` backend support for the detector, and `depthai-nodes==0.6.1` plus the ONNX Runtime OakApp base image for the CLIP text encoder
- `Input:` camera frames by default or `ReplayVideo` via `--media_path`
- `Output:` `Detections` and `Video`
- `Models:` [depthai_models/yolo_world_l.RVC4.yaml](depthai_models/yolo_world_l.RVC4.yaml)
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [utils/helper_functions.py](utils/helper_functions.py)
- [utils/detections_label_mapper.py](utils/detections_label_mapper.py)
- [utils/arguments.py](utils/arguments.py)

## Architecture

- [utils/helper_functions.py](utils/helper_functions.py) converts the configured class names into text embeddings before the pipeline starts.
- The CLIP text-encoder session uses `depthai_nodes.runtime.qnn_session` on the OAK4 DSP when packaged with the ONNX Runtime base image.
- `ParsingNeuralNetwork` is wired manually as a multi-input model with image and text inputs.
- The text tensor is sent once through `inputs["texts"]` and then reused.
- `ImgDetectionsFilter` and [utils/detections_label_mapper.py](utils/detections_label_mapper.py) keep only the configured prompt labels and map them back to their class names.

## Constraints

- [main.py](main.py) enforces `MAX_NUM_CLASSES = 80`.
- This example is effectively RVC4-only and uses the `snpe` DSP backend explicitly.
- Standalone packaging must retain the QNN NPU devices and `/opt/luxonis/npu-runtime` mount in [oakapp.toml](oakapp.toml) for the CLIP text encoder.
- Text prompts are static for the lifetime of the run; there is no service/UI layer to update them dynamically.

## Related Examples

- [custom-frontend/open-vocabulary-object-detection](https://github.com/luxonis/oak-examples/tree/main/custom-frontend/open-vocabulary-object-detection): use this when you need runtime prompt updates and a custom frontend
- [neural-networks/object-detection/yolo-host-decoding](https://github.com/luxonis/oak-examples/tree/main/neural-networks/object-detection/yolo-host-decoding): use this when you need host-side YOLO decode logic instead of prompt embeddings
- [neural-networks/generic-example](https://github.com/luxonis/oak-examples/tree/main/neural-networks/generic-example): use this when you need the simpler fixed-model single-input scaffold

## Validation

- `Run:` `python3 main.py --class_names person car`
- `Success looks like:` the Visualizer shows `Video` and `Detections`, and only the prompted classes are emitted
- `Common failure meaning:` too many classes were requested, the run is on non-RVC4 hardware, or the prompt tensor does not match the selected model
