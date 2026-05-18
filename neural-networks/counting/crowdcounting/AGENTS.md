# AGENTS.md

## Summary

This is the repository reference for density-map-based crowd counting. Use it when you need aggregate crowd estimation from one model output rather than tracked objects or per-person detections.

## Use This Example When

- You need a crowd-density map and a total count.
- You want a single-model counting flow with overlay output.
- You need camera or replay input with a packaged standalone path.

## Do Not Use This Example When

- You need line crossing, directional flow, or track IDs.
- You need person detections as the primary output.
- You need stereo depth or privacy-preserving depth-only counting.

## Quick Facts

- `Category:` `neural-networks/counting/crowdcounting`
- `Shape:` `script+standalone`
- `Primary task:` density-map crowd counting
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` RVC2 peripheral, RVC4 peripheral, and RVC4 standalone packaging
- `Requires:` DM-Count-style model output compatible with the parser
- `Input:` camera frames by default or `ReplayVideo` via `--media_path`
- `Output:` `VideoOverlay` and `Count`
- `Models:` default DM-Count YAMLs in [depthai_models/](depthai_models/)
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [utils/annotation_node.py](utils/annotation_node.py)
- [utils/arguments.py](utils/arguments.py)

## Architecture

- `ParsingNeuralNetwork` runs the counting model on camera or replay input.
- `ApplyColormap` colorizes the density map output.
- `ImgFrameOverlay` blends the density map with the passthrough image.
- [utils/annotation_node.py](utils/annotation_node.py) converts the density output into a count annotation topic.

## Constraints

- This is aggregate counting, not detection or tracking.
- Overlay output assumes the model emits an image-like density map.
- Default FPS is intentionally low, especially on RVC2.

## Related Examples

- [neural-networks/counting/people-counter](https://github.com/luxonis/oak-examples/tree/main/neural-networks/counting/people-counter): use this when you need counts derived from person detections
- [neural-networks/counting/cumulative-object-counting](https://github.com/luxonis/oak-examples/tree/main/neural-networks/counting/cumulative-object-counting): use this when you need line-crossing counts
- [neural-networks/generic-example](https://github.com/luxonis/oak-examples/tree/main/neural-networks/generic-example): use this when you want the simpler single-model scaffold

## Validation

- `Run:` `python3 main.py`
- `Success looks like:` the Visualizer shows a density overlay in `VideoOverlay` and a numeric count in `Count`
- `Common failure meaning:` the selected model output is incompatible with the overlay/count logic or the input source is not producing frames
