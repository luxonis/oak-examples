# AGENTS.md

## Summary

This is the best reference in the repo for lossless digital zoom implemented as crop control around a detected face. Use it when you need device-side crop generation and a face-centered zoom window without changing the camera lens.

## Use This Example When

- You need a reference for `ImageManipConfig` crop updates driven by detections.
- You want to zoom into the first detected face while keeping the source sensor at high resolution.
- You need a simple camera-controls example that also supports replaying a media file in peripheral mode.
- You want a packaged baseline for crop-based face framing rather than focus actuation.

## Do Not Use This Example When

- You need autofocus or exposure control rather than crop control.
- You need a custom frontend or ROS app.
- You need a general object detector instead of a fixed face-detection zoom demo.
- You need segmentation-aware cropping or a multi-stage high-detail pipeline.

## Quick Facts

- `Category:` `camera-controls/lossless-zooming`
- `Shape:` `script+standalone`
- `Primary task:` face-centered crop control for lossless digital zoom
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` RVC2 peripheral, RVC4 peripheral, and RVC4 standalone packaging
- `Requires:` a Luxonis device or replay media file; high-resolution source frames; YuNet model assets
- `Input:` live camera by default or `ReplayVideo` when `--media_path` is used
- `Output:` `Video`, `Visualizations`, and `Cropped Face`
- `Models:` platform-specific YuNet descriptors in [depthai_models/](depthai_models/)
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [main.py](main.py): camera or replay input, face detection, crop config generation, and encoded outputs
- [utils/crop_face.py](utils/crop_face.py): host node that turns the first face detection into crop configs
- [utils/arguments.py](utils/arguments.py): CLI surface
- [depthai_models/yunet.RVC2.yaml](depthai_models/yunet.RVC2.yaml): RVC2 model descriptor
- [depthai_models/yunet.RVC4.yaml](depthai_models/yunet.RVC4.yaml): RVC4 model descriptor
- [backend-run.sh](backend-run.sh): standalone backend command
- [oakapp.toml](oakapp.toml): standalone packaging path

## Architecture

- The example starts from a live camera or a replayed video file.
- A preprocessing `ImageManip` resizes frames into the detector input size.
- A `ParsingNeuralNetwork` runs YuNet face detection.
- The custom [utils/crop_face.py](utils/crop_face.py) host node looks at the first detection, smooths the crop center over recent frames, and emits `ImageManipConfig` updates.
- A second `ImageManip` applies those crop configs to the original high-resolution source frames.
- Encoders publish the detector-view `Video` stream and the zoomed `Cropped Face` stream.

## Data Flow

- `camera or ReplayVideo -> detector ImageManip -> YuNet -> Visualizations`
- `YuNet detections -> CropFace host node -> crop config`
- `original source frames + crop config -> crop ImageManip -> Cropped Face`
- `YuNet passthrough -> encode -> Video`

## Modification Guide

- `Safe to change:` target crop size, averaging window, default FPS, topic names, replay usage
- `Requires care:` hardcoded source-size assumptions, first-detection-only behavior, `ImageManipConfig` timing, replay-versus-camera frame types
- `Likely to break if changed blindly:` crop synchronization, crop-size normalization, or platform-specific frame-type handling

## Common Adaptations

- `To change the zoom window size:` edit `target_size` in [main.py](main.py) and [utils/crop_face.py](utils/crop_face.py)
- `To smooth more or less aggressively:` change `AVG_MAX_NUM` in [utils/crop_face.py](utils/crop_face.py)
- `To follow a different detection policy:` replace the "first detection" logic in [utils/crop_face.py](utils/crop_face.py)
- `To compare against a higher-level face-detail app:` see [apps/focused-vision](https://github.com/luxonis/oak-examples/tree/main/apps/focused-vision)

## Constraints

- The crop logic assumes a source size of `3840x2880` and a target size of `1920x1088`.
- Only the first detected face is used for zooming.
- When no face is detected, `CropFace` sends `setSkipCurrentImage(True)` and the crop branch intentionally skips that frame.
- In standalone mode, the default packaged path uses camera input; `--media_path` is mainly a peripheral-mode workflow unless you edit the app config.

## Non-Obvious Repo Conventions

- Default FPS is platform-dependent when not provided: `30` on RVC4 and `5` on RVC2.
- The detector input frame type differs by platform: `BGR888i` on RVC4 and `BGR888p` on RVC2.
- `crop_manip.inputConfig.setReusePreviousMessage(False)` is an important synchronization requirement for this example.
- `Cropped Face` is an encoded crop stream, not a decoded image topic.

## Related Examples

- [camera-controls/manual-camera-control](https://github.com/luxonis/oak-examples/tree/main/camera-controls/manual-camera-control): use this when you need direct camera tuning instead of crop control
- [camera-controls/depth-driven-focus](https://github.com/luxonis/oak-examples/tree/main/camera-controls/depth-driven-focus): use this when you want the lens to follow face distance instead of cropping the frame
- [apps/focused-vision](https://github.com/luxonis/oak-examples/tree/main/apps/focused-vision): use this when you need more advanced high-detail face handling than a single crop window
- [tutorials/full-fov-nn](https://github.com/luxonis/oak-examples/tree/main/tutorials/full-fov-nn): use this when the broader topic is resolution and field-of-view handling

## Validation

- `Run:` `python3 main.py`
- `Media replay run:` `python3 main.py --media_path <PATH_TO_VIDEO>`
- `Standalone run:` `oakctl app run .`
- `Success looks like:` the Visualizer shows the detector-view `Video`, face `Visualizations`, and a stable `Cropped Face` stream that follows the detected face
- `Common failure meaning:` the source resolution does not match the crop assumptions, no face is being detected, or crop-config timing drifted from the source frames
