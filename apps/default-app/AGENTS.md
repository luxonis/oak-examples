# AGENTS.md

## Summary

This is the baseline packaged application in the repository. It is the best reference when you need one app-shaped example that combines RGB video, encoded streaming, object detections, and optional stereo depth without introducing a custom frontend.

## Use This Example When

- You need a packaged DepthAI app rather than a one-off script.
- You want a compact reference for RGB preview, H.264 output, detections, and optional depth in one place.
- You need a baseline that works in peripheral mode and also has an RVC4 standalone packaging path.
- You want the simplest starting point under `apps/` before moving to a more specialized app.

## Do Not Use This Example When

- You need a custom browser UI or frontend/backend service interaction.
- You need spatial detections fused into one composed view.
- You need ROS, C++, or multi-device behavior.
- You need a task-specific multi-stage pipeline rather than a baseline app shell.

## Quick Facts

- `Category:` `apps/default-app`
- `Shape:` `script+standalone`
- `Primary task:` packaged RGB + detections + optional stereo depth baseline
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` RVC2 peripheral, RVC4 peripheral, and RVC4 standalone packaging
- `Requires:` a Luxonis device; stereo depth branch only appears on devices with two mono cameras
- `Input:` RGB camera on `CAM_A`; optional mono stereo pair discovered from connected camera features
- `Output:` `Raw video`, `Video H264`, `Detections`, and optional `Depth`
- `Models:` platform-specific YOLOv6 Nano descriptors in [depthai_models/](depthai_models/)
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [main.py](main.py): full pipeline, platform branching, encoder setup, and optional stereo logic
- [utils/arguments.py](utils/arguments.py): CLI surface
- [depthai_models/yolov6_nano_r2_coco.RVC2.yaml](depthai_models/yolov6_nano_r2_coco.RVC2.yaml): default RVC2 model descriptor
- [depthai_models/yolov6_nano_r2_coco.RVC4.yaml](depthai_models/yolov6_nano_r2_coco.RVC4.yaml): default RVC4 model descriptor
- [backend-run.sh](backend-run.sh): backend command used in standalone mode
- [oakapp.toml](oakapp.toml): standalone packaging and model bundle wiring

## Architecture

- The script creates one `dai.Device` and one `dai.RemoteConnection`.
- It resolves a platform-specific YOLOv6 Nano YAML and builds a `DetectionNetwork`.
- `CAM_A` provides RGB frames for inference, preview, and encoding.
- A `VideoEncoder` publishes an H.264 stream.
- If two mono cameras are present, the script builds a `StereoDepth` branch and publishes a colorized depth output.
- RVC4 uses `ImageAlign` for RGB-depth alignment; RVC2 uses `StereoDepth.setDepthAlign(...)`.

## Data Flow

- `CAM_A -> DetectionNetwork -> Detections`
- `CAM_A -> NV12 output -> VideoEncoder -> Video H264`
- `CAM_A -> NV12 output -> Raw video`
- `mono pair -> StereoDepth -> ApplyDepthColormap -> Depth` when stereo cameras are available

## Modification Guide

- `Safe to change:` encoder profile, topic names, IR projector usage, RGB output sizes, model YAML defaults
- `Requires care:` platform-specific RVC2 versus RVC4 NN wiring, stereo alignment logic, mono camera discovery, encoded stream size assumptions
- `Likely to break if changed blindly:` removing the platform branch, assuming every device has stereo cameras, changing model filenames without updating `main.py`

## Common Adaptations

- `To swap the default detector:` change the platform YAML files in [depthai_models/](depthai_models/) or point `main.py` at another descriptor
- `To remove depth:` keep only the RGB and detection branches in [main.py](main.py)
- `To change encoded output:` edit the `VideoEncoder` settings in [main.py](main.py)
- `To build a richer app:` start here for packaging shape, then compare against [apps/conference-demos/rgb-depth-connections](https://github.com/luxonis/oak-examples/tree/main/apps/conference-demos/rgb-depth-connections) or [custom-frontend/raw-stream](https://github.com/luxonis/oak-examples/tree/main/custom-frontend/raw-stream)

## Constraints

- Stereo output is conditional and will not exist on RGB-only devices.
- The script assumes the main RGB camera is on `CAM_A`.
- `device.setIrLaserDotProjectorIntensity(1)` may fail on devices that do not expose that feature.
- RVC4 and RVC2 use different depth alignment paths, so treat the stereo branch as platform-specific code.

## Non-Obvious Repo Conventions

- [oakapp.toml](oakapp.toml) adds an RVC4 standalone path but does not make the example standalone-only.
- `assign_frontend_port = true` is present in [oakapp.toml](oakapp.toml), but this example still uses the default Visualizer rather than a custom frontend.
- The model YAML is loaded by filename in the example directory, not by an explicit `depthai_models/...` path string.
- Depth is added only after runtime camera feature discovery, not by a fixed device compatibility table in code.

## Related Examples

- [neural-networks/generic-example](https://github.com/luxonis/oak-examples/tree/main/neural-networks/generic-example): use this when you want a more generic single-model scaffold
- [apps/conference-demos/rgb-depth-connections](https://github.com/luxonis/oak-examples/tree/main/apps/conference-demos/rgb-depth-connections): use this when you need a composed RGB-depth visualization with spatial detections
- [neural-networks/object-detection/spatial-detections](https://github.com/luxonis/oak-examples/tree/main/neural-networks/object-detection/spatial-detections): use this when spatial coordinates matter more than baseline app packaging
- [tutorials/camera-demo](https://github.com/luxonis/oak-examples/tree/main/tutorials/camera-demo): use this when you want a smaller camera-streaming baseline

## Validation

- `Run:` `python3 main.py`
- `Standalone run:` `oakctl app run .`
- `Success looks like:` the Visualizer shows `Raw video`, `Video H264`, `Detections`, and optionally `Depth`
- `Common failure meaning:` device connection failed, the expected model YAML is missing, or the device has no stereo mono pair for the depth branch
