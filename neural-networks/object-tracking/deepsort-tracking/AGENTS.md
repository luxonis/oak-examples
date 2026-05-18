# AGENTS.md

## Summary

This is the repository reference for DeepSORT-style tracking using detector outputs plus OSNet embeddings. Use it when you need embedding-based tracking rather than the built-in object tracker alone.

## Use This Example When

- You need detector plus re-identification embeddings for tracking.
- You want a host-side DeepSORT pattern.
- You need camera or replay input with a packaged standalone path.

## Do Not Use This Example When

- You only need built-in `ObjectTracker`.
- You need stereo spatial tracking rather than RGB embedding tracking.
- You need a single-stage detector with no crop/embedding branch.

## Quick Facts

- `Category:` `neural-networks/object-tracking/deepsort-tracking`
- `Shape:` `script+standalone`
- `Primary task:` DeepSORT-style tracking from detections plus embeddings
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` RVC2 peripheral, RVC4 peripheral, and RVC4 standalone packaging
- `Requires:` detector model, OSNet embedding model, and host-side tracking logic
- `Input:` camera frames by default or `ReplayVideo` via `--media_path`
- `Output:` `Video` and `Detections`
- `Models:` YOLOv6 and OSNet YAMLs in [depthai_models/](depthai_models/)
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [utils/deepsort_tracking.py](utils/deepsort_tracking.py)
- [utils/visualized_tracklets.py](utils/visualized_tracklets.py)
- [utils/arguments.py](utils/arguments.py)

## Architecture

- A detector runs on a larger requested frame to preserve detail for the embedding stage.
- `FrameCropper` extracts detection crops for OSNet.
- `GatherData` re-associates embeddings with the original detections.
- [utils/deepsort_tracking.py](utils/deepsort_tracking.py) performs the host-side tracking and outputs annotated detections.

## Constraints

- This is a host-tracker example; it is heavier and more stateful than examples that use only `ObjectTracker`.
- `REQ_WIDTH = 1024` and `REQ_HEIGHT = 768` are chosen deliberately for the two-stage crop flow.
- Tracking quality depends on both the detector and embedding model, not on one stage alone.

## Related Examples

- [neural-networks/object-tracking/people-tracker](https://github.com/luxonis/oak-examples/tree/main/neural-networks/object-tracking/people-tracker): use this when you want person tracking with the built-in tracker and counting logic
- [neural-networks/reidentification/human-reidentification](https://github.com/luxonis/oak-examples/tree/main/neural-networks/reidentification/human-reidentification): use this when the task is identity matching rather than online tracking
- [neural-networks/object-tracking/kalman](https://github.com/luxonis/oak-examples/tree/main/neural-networks/object-tracking/kalman): use this when you need smoothed tracklets from spatial detections instead of embedding-based tracking

## Validation

- `Run:` `python3 main.py`
- `Success looks like:` the Visualizer shows `Video` and `Detections`, and IDs remain more stable across motion and occlusion than plain detector boxes
- `Common failure meaning:` detector crops are poor, embedding outputs are mismatched to detections, or the host tracker is overloaded for the requested FPS
