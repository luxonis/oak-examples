# AGENTS.md

## Summary

This is the repository reference for sending Hub snaps from detection-driven conditions. Use it when you need a packaged example that filters detections, throttles events over time, and uploads frames plus metadata to Luxonis Hub.

## Use This Example When

- You need automatic snap collection into Luxonis Hub.
- You want a detection-triggered dataset collection flow rather than a local export flow.
- You need a compact script that supports either live camera input or replayed media.
- You want a baseline that already wires `SnapsUploader` into a DepthAI pipeline.

## Do Not Use This Example When

- You need a richer custom frontend or browser UI.
- You need Roboflow dataset export rather than Hub snaps.
- You need a complex rule engine with per-class custom metadata.
- You need a generic detection baseline with no external side effects.

## Quick Facts

- `Category:` `integrations/hub-snaps-events`
- `Shape:` `script+standalone`
- `Primary task:` upload Hub snaps when filtered detections are present
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` RVC2 peripheral, RVC4 peripheral, and RVC4 standalone packaging
- `Requires:` Hub API key, Luxonis device or replay media, and the bundled YOLOv6 Nano model
- `Input:` live camera frames by default or `ReplayVideo` input via `--media_path`
- `Output:` `Video`, `Visualizations`, and Hub snap uploads as a side effect
- `Models:` `yolov6_nano_r2_coco.<platform>.yaml` in [depthai_models/](depthai_models/)
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`, with collected snaps visible in Hub

## Read First

- [README.md](README.md): overall usage and Hub workflow
- [main.py](main.py): pipeline setup, API-key handling, filtering, and uploader wiring
- [utils/arguments.py](utils/arguments.py): CLI surface for classes, threshold, media path, and time interval
- [utils/snaps_producer.py](utils/snaps_producer.py): the host node that decides when to emit snap events
- [oakapp.toml](oakapp.toml): standalone packaging and placeholder API-key entrypoint

## Architecture

- `main.py` loads `.env` first through `load_dotenv(override=True)`.
- If `--api_key` is passed, it overwrites `DEPTHAI_HUB_API_KEY` at runtime.
- A platform-specific YOLOv6 Nano archive is loaded from [depthai_models/](depthai_models/).
- The input source is either:
  - a live camera node
  - a `ReplayVideo` node when `--media_path` is used
- `ParsingNeuralNetwork` produces detections plus passthrough frames.
- `ImgDetectionsFilter` keeps only configured labels and detections above the configured confidence threshold.
- The custom [utils/snaps_producer.py](utils/snaps_producer.py) host node time-throttles snap emission.
- `SnapsUploader` handles the actual upload to Hub.

## Data Flow

- `camera or replay -> ParsingNeuralNetwork -> detections + passthrough`
- `detections -> ImgDetectionsFilter -> filtered detections`
- `passthrough + filtered detections -> SnapsProducer -> SnapData`
- `SnapData -> SnapsUploader -> Hub upload`
- `passthrough -> Video`
- `filtered detections -> Visualizations`

## Modification Guide

- `Safe to change:` time interval, tracked classes, topic names, replay usage, confidence threshold default
- `Requires care:` environment/API-key handling, label mapping against model metadata, and any custom Hub metadata payload
- `Likely to break if changed blindly:` model filename loading, standalone entrypoint arguments, or assumptions about what detections are being filtered in or out

## Common Adaptations

- `To trigger on different classes:` adjust `--class_names` handling or the default list in [utils/arguments.py](utils/arguments.py)
- `To customize snap metadata:` edit `snap_name`, `tags`, and `extras` in [utils/snaps_producer.py](utils/snaps_producer.py)
- `To change upload cadence:` edit `time_interval` handling in [utils/snaps_producer.py](utils/snaps_producer.py)
- `To switch to another dataset sink:` compare this with [integrations/roboflow-dataset](https://github.com/luxonis/oak-examples/tree/main/integrations/roboflow-dataset) and replace the uploader stage

## Constraints

- The current code uploads when detections are present at or above `minConfidence`; this is the opposite of the README sentence that describes “low-confidence” snaps.
- [utils/snaps_producer.py](utils/snaps_producer.py) currently hardcodes `snap_name="test_snap"`, `tags=["test_tag"]`, and placeholder `extras`.
- The host node only checks “filtered detections exist and enough time has passed”; it does not implement richer per-detection or per-scene logic.
- [oakapp.toml](oakapp.toml) hardcodes `--api_key <API_KEY>` in the standalone entrypoint, so packaged runs require manual editing before they are usable.

## Non-Obvious Repo Conventions

- `.env` is loaded with `override=True`, so values in the local `.env` file replace existing environment values unless the CLI argument is used afterward.
- `main.py` loads the model YAML by bare filename, relying on the example working directory or the packaged `depthai_models` mount.
- `Visualizations` is an annotation topic layered over the preview stream; it is not a separate rendered image pipeline.

## Related Examples

- [integrations/roboflow-dataset](https://github.com/luxonis/oak-examples/tree/main/integrations/roboflow-dataset): use this when you need automatic detections exported into a Roboflow dataset instead of Hub
- [apps/data-collection](https://github.com/luxonis/oak-examples/tree/main/apps/data-collection): use this when you want a richer standalone collection app rather than a small integration script
- [apps/default-app](https://github.com/luxonis/oak-examples/tree/main/apps/default-app): use this when you need a simpler packaged detection baseline with no Hub upload side effect
- [integrations/roboflow-workflow](https://github.com/luxonis/oak-examples/tree/main/integrations/roboflow-workflow): use this when the external integration target is a live Roboflow Workflow rather than Hub collection

## Validation

- `Run:` `python3 main.py --api_key <API_KEY>`
- `Standalone run:` edit [oakapp.toml](oakapp.toml), then run `oakctl app run .`
- `Success looks like:` the Visualizer shows `Video` and `Visualizations`, and new snaps appear in Hub after the configured time interval when filtered detections are present
- `Common failure meaning:` API-key setup is wrong, the model bundle is unavailable, the configured class names are not produced by the model, or the README’s threshold description was followed instead of the actual current code
