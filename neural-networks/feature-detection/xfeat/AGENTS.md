# AGENTS.md

## Summary

This is the repository reference for XFeat-based local feature extraction and matching. Use it when you need keypoint/descriptor matching rather than detections, pose, or depth.

## Use This Example When

- You need local feature matching.
- You want to compare mono reference-frame matching and stereo left/right matching.
- You need a packaged example that can switch behavior based on the selected XFeat model.

## Do Not Use This Example When

- You need detections, tracking IDs, or pose estimation.
- You need a generic single-model visualizer flow.
- You need a replay-media path; this example is live-camera oriented.

## Quick Facts

- `Category:` `neural-networks/feature-detection/xfeat`
- `Shape:` `script+standalone`
- `Primary task:` feature extraction and matching in mono or stereo XFeat mode
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` RVC2 peripheral, RVC4 peripheral, and RVC4 standalone packaging; stereo mode requires `CAM_B/C`
- `Requires:` XFeat mono or stereo model and matching camera topology
- `Input:` live camera in mono mode or stereo pair in stereo mode
- `Output:` mono `Matches`, or stereo `Left Camera`, `Right Camera`, and `Matches`
- `Models:` XFeat mono/stereo YAMLs in [depthai_models/](depthai_models/)
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [mono.py](mono.py)
- [stereo.py](stereo.py)
- [utils/custom_visualizer.py](utils/custom_visualizer.py)
- [utils/arguments.py](utils/arguments.py)

## Architecture

- `main.py` inspects the selected model parser and dispatches into [mono.py](mono.py) or [stereo.py](stereo.py).
- Mono mode runs one camera through `NeuralNetwork`, parses with `XFeatMonoParser`, and lets the user capture a reference frame with `s`.
- Stereo mode runs separate left/right networks on `CAM_B` and `CAM_C`, parses with `XFeatStereoParser`, and renders match lines between the two streams.

## Constraints

- The default model is `luxonis/xfeat:mono-320x240`, so stereo mode is only reached when a stereo-parser model is selected.
- Mono mode depends on the user pressing `s` to establish the reference frame.
- Stereo mode requires at least two cameras and is hardwired to `CAM_B` and `CAM_C`.

## Related Examples

- [neural-networks/object-tracking/deepsort-tracking](https://github.com/luxonis/oak-examples/tree/main/neural-networks/object-tracking/deepsort-tracking): use this when you need tracking based on detections and embeddings instead of local feature matches
- [neural-networks/generic-example](https://github.com/luxonis/oak-examples/tree/main/neural-networks/generic-example): use this when you only need the generic single-model scaffold
- [depth-measurement/triangulation](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/triangulation): use this when you need stereo correspondence for 3D measurement rather than generic feature matching

## Validation

- `Run:` `python3 main.py`
- `Success looks like:` mono mode shows `Matches` after `s` sets a reference frame, or stereo mode shows left/right streams plus match visualization
- `Common failure meaning:` the wrong model variant was selected, stereo mode was used without the required camera pair, or no reference frame was set in mono mode
