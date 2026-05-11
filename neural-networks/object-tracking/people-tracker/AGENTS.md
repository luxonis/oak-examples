# AGENTS.md

## Summary

This is the repository reference for directional people flow counting with tracked person detections. Use it when you need up/down/left/right totals rather than generic tracked objects.

## Use This Example When

- You need directional people-flow counts.
- You want built-in tracking plus a host-side counting overlay.
- You need camera or replay input with person-only logic.

## Do Not Use This Example When

- You need generic object tracking.
- You need stereo spatial tracking.
- You only need the current number of people in frame.

## Quick Facts

- `Category:` `neural-networks/object-tracking/people-tracker`
- `Shape:` `script+standalone`
- `Primary task:` directional people flow counting from tracked detections
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` RVC2 peripheral, RVC4 peripheral, and RVC4 standalone packaging
- `Requires:` person detector, object tracker, and optional replay input
- `Input:` camera frames by default or `ReplayVideo` via `--media_path`
- `Output:` `Video`, `Tracklets`, and `People count`
- `Models:` SCRFD person-detection YAMLs in [depthai_models/](depthai_models/)
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [utils/people_counter.py](utils/people_counter.py)
- [utils/tracklet_visualizer.py](utils/tracklet_visualizer.py)
- [utils/arguments.py](utils/arguments.py)

## Architecture

- `ParsingNeuralNetwork` runs the person detector.
- `ObjectTracker` maintains tracklets with a tracker threshold of `0.4`.
- [utils/tracklet_visualizer.py](utils/tracklet_visualizer.py) renders the tracked boxes.
- [utils/people_counter.py](utils/people_counter.py) converts tracklet motion into directional counts using the configured threshold.

## Constraints

- This example is person-specific and assumes label `0` is the person class for the selected model.
- Direction counts depend on tracker continuity and the configured threshold, not just detector quality.
- There is no stereo branch; this is 2D tracking and flow counting only.

## Related Examples

- [../../counting/people-counter](../../counting/people-counter/): use this when you only need a current-frame person count
- [../../counting/cumulative-object-counting](../../counting/cumulative-object-counting/): use this when you want generic object line crossing
- [../deepsort-tracking](../deepsort-tracking/): use this when you need embedding-based tracking rather than simple person flow counting

## Validation

- `Run:` `python3 main.py`
- `Success looks like:` the Visualizer shows tracked people and directional totals that change as people move through the frame
- `Common failure meaning:` the selected model does not match the hardcoded label assumption, the tracker is unstable, or the threshold is inappropriate for the scene geometry
