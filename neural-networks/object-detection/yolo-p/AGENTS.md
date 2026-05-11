# AGENTS.md

## Summary

This is the repository reference for ADAS-style YOLO-P output: detections plus road and lane segmentation. Use it when you need one model with multiple driving-scene outputs rather than a plain detector.

## Use This Example When

- You need road and lane segmentation along with vehicle detections.
- You want a multi-output parser-backed object-detection example.
- You need camera or replay input with a packaged standalone path.

## Do Not Use This Example When

- You only need object detections.
- You need open-vocabulary prompts or host-side decode logic.
- You need a stereo spatial workflow.

## Quick Facts

- `Category:` `neural-networks/object-detection/yolo-p`
- `Shape:` `script+standalone`
- `Primary task:` ADAS-style detection plus road/lane segmentation
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` RVC2 peripheral, RVC4 peripheral, and RVC4 standalone packaging
- `Requires:` YOLO-P model and input resized to model dimensions
- `Input:` camera frames by default or `ReplayVideo` via `--media_path`
- `Output:` `Road Segmentation` and `Detections`
- `Models:` YOLO-P YAMLs in [depthai_models/](depthai_models/)
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [utils/annotation_node.py](utils/annotation_node.py)
- [utils/arguments.py](utils/arguments.py)

## Architecture

- `ParsingNeuralNetwork` runs the YOLO-P multi-head model on camera or replay input.
- [utils/annotation_node.py](utils/annotation_node.py) consumes three outputs:
  - detections
  - road segmentation
  - lane segmentation
- The Visualizer exposes the segmentation composite and detection overlay separately.

## Constraints

- The example resizes input directly to the model shape; it is not preserving original aspect ratio.
- Output interpretation depends on the current multi-head order in [main.py](main.py).
- This is a specialized ADAS example, not a general segmentation baseline.

## Related Examples

- [../yolo-world](../yolo-world/): use this when you need configurable class prompts instead of fixed ADAS outputs
- [../spatial-detections](../spatial-detections/): use this when you need stereo spatial coordinates with detections
- [../../segmentation/depth-crop](../../segmentation/depth-crop/): use this when the segmentation output should interact with stereo depth

## Validation

- `Run:` `python3 main.py`
- `Success looks like:` the Visualizer shows `Road Segmentation` and `Detections`, with lane/road overlays and detected vehicles
- `Common failure meaning:` the model output ordering changed, the replay input was resized incorrectly, or the operator expected a generic single-output detector
