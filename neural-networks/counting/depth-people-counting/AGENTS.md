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
- You need a single RGB video replay path. Replay here is a holistic stereo recording.

## Quick Facts

- `Category:` `neural-networks/counting/depth-people-counting`
- `Shape:` `script+standalone`
- `Primary task:` count people crossing a virtual line using disparity-derived detections
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` stereo-capable devices with `CAM_B` and `CAM_C`; standalone packaging also exists
- `Requires:` stereo pair, or a holistic recording from `record.py` (`recording_<time>.tar.gz`)
- `Input:` live `CAM_B` and `CAM_C`, or the same sockets replayed from a holistic archive
- `Output:` `Disparity` and `Count`
- `Models:` none
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [utils/disparity_to_dets.py](utils/disparity_to_dets.py)
- [utils/annotation_node.py](utils/annotation_node.py)
- [record.py](record.py)

## Architecture

- Live mode uses stereo mono cameras on `CAM_B` and `CAM_C` at 640x400 `GRAY8`.
- Replay mode calls `pipeline.enableHolisticReplay` on a `record.py` archive, then builds those same camera nodes. The archive's `camera_info.json` supplies calibration. Recorded sequence numbers and device timestamps are kept on the first pass. Do not rebuild the pair with `ReplayVideo` plus a host timestamp editor.
- `StereoDepth` produces disparity, which [utils/disparity_to_dets.py](utils/disparity_to_dets.py) converts into pseudo-detections inside a fixed ROI.
- `ObjectTracker` tracks those pseudo-detections, and [utils/annotation_node.py](utils/annotation_node.py) counts line crossings.

## Constraints

- Replay expects `recording_<time>.tar.gz` (or that archive extracted, with `camera_info.json`, `CameraCAM_B`, and `CameraCAM_C`). `recordings/demo` is the old renamed-MP4 layout and is rejected.
- `record.py` requests 640x400. The SDK may store a larger aligned sensor mode inside the archive. Replay resizes back to 640x400 through the camera node.
- The recording is H.264. Replayed disparity can differ slightly from the live frames. FFV1 AVI is rejected by `ReplayVideo` on this library.
- The detection ROI is hardcoded in [main.py](main.py) to `(50, 50, 550, 350)`.
- This example counts moving disparity blobs; it does not know object classes.

## Related Examples

- [neural-networks/counting/cumulative-object-counting](https://github.com/luxonis/oak-examples/tree/main/neural-networks/counting/cumulative-object-counting): use this when you want RGB detection plus tracking for line crossing
- [neural-networks/object-detection/spatial-detections](https://github.com/luxonis/oak-examples/tree/main/neural-networks/object-detection/spatial-detections): use this when you need semantic detections with stereo
- [depth-measurement/stereo-on-host](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/stereo-on-host): use this when the focus is host stereo processing rather than counting

## Validation

- `Run:` `python3 main.py`
- `Record:` `python3 record.py --output recordings`
- `Replay run:` `python3 main.py --media_path recordings/recording_<time>.tar.gz`
- `Success looks like:` the Visualizer shows `Disparity` and `Count`, and tracked disparity blobs increment counts when they cross the configured line. `Replay enabled` is an info line. A failed setup warns `Replay disabled` or `Could not set up holistic replay`.
- `Common failure meaning:` the path is not a holistic archive, the archive is missing `CAM_B` or `CAM_C`, stereo quality is poor, or the fixed ROI does not match the walkway scene
