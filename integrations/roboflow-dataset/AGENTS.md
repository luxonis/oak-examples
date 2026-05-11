# AGENTS.md

## Summary

This is the repository reference for building a Roboflow dataset from live DepthAI detections. Use it when you want a packaged detection pipeline that can upload image-plus-annotation pairs to Roboflow either manually or on an interval.

## Use This Example When

- You need automatic or semi-automatic dataset collection into Roboflow.
- You want detections from a device model turned into image annotations with minimal extra code.
- You need a small host-node example that performs uploads asynchronously.
- You want a packaged script that supports both camera input and replayed media.

## Do Not Use This Example When

- You need Hub snaps rather than Roboflow dataset uploads.
- You need a custom browser frontend.
- You need a general-purpose detector with no external upload side effects.
- You need a workflow/external inference integration rather than device-side detections.

## Quick Facts

- `Category:` `integrations/roboflow-dataset`
- `Shape:` `script+standalone`
- `Primary task:` upload detection-labeled frames into a Roboflow project
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` RVC2 peripheral, RVC4 peripheral, and RVC4 standalone packaging
- `Requires:` Roboflow API key, workspace name, dataset/project name, Luxonis device or replay media, and bundled YOLOv6 Nano model
- `Input:` live camera frames by default or `ReplayVideo` via `--media_path`
- `Output:` `Video`, `Detections`, and Roboflow uploads as a side effect
- `Models:` `yolov6_nano_r2_coco.<platform>.yaml` in [depthai_models/](depthai_models/)
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`, with upload control on keyboard

## Read First

- [README.md](README.md): Roboflow setup and CLI usage
- [main.py](main.py): pipeline setup, uploader construction, and keyboard loop
- [utils/arguments.py](utils/arguments.py): required credentials and auto-upload flags
- [utils/roboflow_node.py](utils/roboflow_node.py): host-side upload trigger logic
- [utils/roboflow_uploader.py](utils/roboflow_uploader.py): Roboflow SDK upload path and VOC XML generation
- [oakapp.toml](oakapp.toml): standalone entrypoint placeholders and packaged model path

## Architecture

- A platform-specific YOLOv6 Nano archive is loaded from [depthai_models/](depthai_models/).
- The input source is either:
  - a live camera node
  - a `ReplayVideo` node when `--media_path` is set
- `ParsingNeuralNetwork` produces the detection stream and passthrough preview frames.
- `RoboflowUploader` wraps the Roboflow SDK and uploads a temporary JPG plus VOC XML annotation file.
- The custom [utils/roboflow_node.py](utils/roboflow_node.py) host node:
  - caches the latest frame and detections
  - optionally auto-uploads at an interval when detections pass a confidence threshold
  - uploads on `space` key press through `handle_key()`
- Uploads are dispatched asynchronously through a `ThreadPoolExecutor`.

## Data Flow

- `camera or replay -> ParsingNeuralNetwork -> detections + passthrough`
- `passthrough + detections -> RoboflowNode -> upload triggers`
- `RoboflowNode -> RoboflowUploader -> JPG + VOC XML upload to Roboflow`
- `passthrough -> Video`
- `detections -> Detections`

## Modification Guide

- `Safe to change:` auto-upload interval default, auto-threshold default, topic names, replay usage
- `Requires care:` Roboflow credential handling, label mapping from model metadata, and upload concurrency
- `Likely to break if changed blindly:` the required CLI credentials, standalone entrypoint placeholders, or VOC annotation generation in [utils/roboflow_uploader.py](utils/roboflow_uploader.py)

## Common Adaptations

- `To switch to another detector:` replace the model YAMLs in [depthai_models/](depthai_models/) and keep the same detection output contract
- `To change annotation format:` replace the VOC XML generation in [utils/roboflow_uploader.py](utils/roboflow_uploader.py)
- `To make manual-only uploads the default:` remove or disable the auto-upload branch in [utils/roboflow_node.py](utils/roboflow_node.py)
- `To switch to Hub instead of Roboflow:` compare against [../hub-snaps-events](../hub-snaps-events/)

## Constraints

- [utils/arguments.py](utils/arguments.py) makes `--api-key`, `--workspace`, and `--dataset` required in peripheral mode.
- Auto-upload only uploads when detections above `--auto-threshold` are present at the sampling interval.
- Manual `space` uploads do not require any detections and can produce empty annotation files.
- [utils/roboflow_node.py](utils/roboflow_node.py) currently uses a `ThreadPoolExecutor(max_workers=40)`, which is aggressive for a small upload helper.
- [oakapp.toml](oakapp.toml) hardcodes placeholder credentials in the standalone entrypoint and must be edited before packaged runs are useful.

## Non-Obvious Repo Conventions

- `main.py` calls `pipeline.processTasks()` in the keyboard loop; keep that behavior in mind if you restructure the host-node flow.
- Uploads are performed through temporary local files rather than direct in-memory API calls.
- Class labels come from the model metadata stored in the loaded NN archive, not from a separate label file in the example.

## Related Examples

- [../hub-snaps-events](../hub-snaps-events/): use this when you want Luxonis Hub snaps instead of Roboflow dataset uploads
- [../roboflow-workflow](../roboflow-workflow/): use this when Roboflow is the live inference engine rather than the dataset sink
- [../../apps/data-collection](../../apps/data-collection/): use this when you want a larger standalone data-collection app rather than a small integration script
- [../../apps/default-app](../../apps/default-app/): use this when you need a packaged detector baseline with no upload logic

## Validation

- `Run:` `python3 main.py --api-key <API_KEY> --workspace <WORKSPACE> --dataset <DATASET>`
- `Auto mode:` add `--auto-interval <SECONDS>`
- `Standalone run:` edit [oakapp.toml](oakapp.toml), then run `oakctl app run .`
- `Success looks like:` the Visualizer shows `Video` and `Detections`, pressing `space` triggers an upload, and Roboflow receives images plus annotations
- `Common failure meaning:` Roboflow credentials are wrong, the configured project/workspace names do not exist, the model bundle is unavailable, or the upload behavior was inferred from the README rather than the actual current host-node logic
