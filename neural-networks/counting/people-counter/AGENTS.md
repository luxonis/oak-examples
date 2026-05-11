# AGENTS.md

## Summary

This is the simplest person-counting reference in the repository. Use it when you only need the number of people visible in the current frame rather than cumulative flow or tracked crossings.

## Use This Example When

- You need a per-frame person count.
- You want a detector-only baseline with a tiny amount of postprocessing.
- You need camera or replay input and a packaged standalone path.

## Do Not Use This Example When

- You need line crossing or directional counts.
- You need trackers or IDs.
- You need depth-only counting.

## Quick Facts

- `Category:` `neural-networks/counting/people-counter`
- `Shape:` `script+standalone`
- `Primary task:` per-frame person counting from detections
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` RVC2 peripheral, RVC4 peripheral, and RVC4 standalone packaging
- `Requires:` SCRFD person detector or compatible model
- `Input:` camera frames by default or `ReplayVideo` via `--media_path`
- `Output:` `Video`, `PersonDetections`, and `PersonCount`
- `Models:` default SCRFD person-detection YAMLs in [depthai_models/](depthai_models/)
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [utils/annotation_node.py](utils/annotation_node.py)
- [utils/arguments.py](utils/arguments.py)

## Architecture

- `ParsingNeuralNetwork` runs the person detector on camera or replay input.
- `ImgDetectionsFilter` keeps only the `person` label and applies a fixed confidence threshold of `0.5`.
- [utils/annotation_node.py](utils/annotation_node.py) converts the filtered detections into a count annotation topic.

## Constraints

- The count is for the current frame only; there is no tracking or de-duplication over time.
- The current code assumes the loaded detector exposes a `person` class in its metadata.
- The filter threshold is fixed in code rather than a CLI argument.

## Related Examples

- [../cumulative-object-counting](../cumulative-object-counting/): use this when you need line-crossing counts
- [../../object-tracking/people-tracker](../../object-tracking/people-tracker/): use this when you need directional person flow
- [../../object-detection/social-distancing](../../object-detection/social-distancing/): use this when you need person detections plus spatial reasoning

## Validation

- `Run:` `python3 main.py`
- `Success looks like:` the Visualizer shows `Video`, `PersonDetections`, and `PersonCount`, and the count follows visible people in the frame
- `Common failure meaning:` the selected model does not expose the expected `person` label or the detector confidence is too unstable for the scene
