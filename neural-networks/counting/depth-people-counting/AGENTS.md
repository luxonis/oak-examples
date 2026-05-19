# AGENTS.md

## Summary

This is the repository reference for privacy-preserving people counting from disparity alone. Use it when you need virtual line counting without RGB detection models.

## Use This Example When

- You need depth-only counting.
- You want line-crossing counts from stereo disparity instead of RGB detections.
- You need a privacy-preserving counting reference.

## Do Not Use This Example When

- You need semantic person detections.
- You need generic stereo depth visualization rather than counting.
- You need a single video-file replay path; this example expects stereo-pair replay assets.

## Quick Facts

- `Category:` `neural-networks/counting/depth-people-counting`
- `Shape:` `script+standalone`
- `Primary task:` count people crossing a virtual line using disparity-derived detections
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` stereo-capable devices with `CAM_B` and `CAM_C`; standalone packaging also exists
- `Requires:` stereo pair, or replay assets with `left.mp4`, `right.mp4`, and `calib.json`
- `Input:` live stereo mono cameras or replayed stereo pair
- `Output:` `Disparity` and `Count`
- `Models:` none
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [utils/disparity_to_dets.py](utils/disparity_to_dets.py)
- [utils/annotation_node.py](utils/annotation_node.py)
- [utils/frame_editor.py](utils/frame_editor.py)

## Architecture

- Live mode uses stereo mono cameras on `CAM_B` and `CAM_C`.
- Replay mode injects stereo calibration and replays left/right mono files separately.
- `StereoDepth` produces disparity, which [utils/disparity_to_dets.py](utils/disparity_to_dets.py) converts into pseudo-detections inside a fixed ROI.
- `ObjectTracker` tracks those pseudo-detections, and [utils/annotation_node.py](utils/annotation_node.py) counts line crossings.

## Constraints

- Replay mode expects a folder-style stereo dataset, not a single video file.
- The detection ROI is hardcoded in [main.py](main.py) to `(50, 50, 550, 350)`.
- This example counts moving disparity blobs; it does not know object classes.

## Related Examples

- [neural-networks/counting/cumulative-object-counting](https://github.com/luxonis/oak-examples/tree/main/neural-networks/counting/cumulative-object-counting): use this when you want RGB detection plus tracking for line crossing
- [neural-networks/object-detection/spatial-detections](https://github.com/luxonis/oak-examples/tree/main/neural-networks/object-detection/spatial-detections): use this when you need semantic detections with stereo
- [depth-measurement/stereo-on-host](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/stereo-on-host): use this when the focus is host stereo processing rather than counting

## Validation

- `Run:` `python3 main.py`
- `Replay run:` point `--media_path` at a folder containing `left.mp4`, `right.mp4`, and `calib.json`
- `Success looks like:` the Visualizer shows `Disparity` and `Count`, and tracked disparity blobs increment counts when they cross the configured line
- `Common failure meaning:` the replay folder is missing stereo assets, stereo quality is poor, or the fixed ROI does not match the walkway scene
