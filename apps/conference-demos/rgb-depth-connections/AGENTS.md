# AGENTS.md

## Summary

This is the best app-shaped reference for composing RGB, depth, and spatial detections into one polished conference-style output. Use it when you need a spatial detection pipeline plus a custom combined visualization, not just separate raw topics.

## Use This Example When

- You need RGB and depth shown side-by-side in one output frame.
- You need spatial detections with a bird's-eye inset.
- You want a host-node reference that postprocesses synced device outputs into a presentation-ready view.
- You need an app that still works in both peripheral mode and RVC4 standalone packaging.

## Do Not Use This Example When

- You only need a baseline detector without composed visualization.
- You need a custom browser frontend or service-based UI.
- You need a minimal stereo example without host-side compositing.
- You need a reusable spatial detection scaffold rather than a fixed demo layout.

## Quick Facts

- `Category:` `apps/conference-demos/rgb-depth-connections`
- `Shape:` `script+standalone`
- `Primary task:` composed RGB + depth + spatial detections visualization
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` stereo-capable devices in peripheral mode; RVC4 standalone packaging also exists
- `Requires:` color camera on `CAM_A`, mono stereo cameras on `CAM_B` and `CAM_C`
- `Input:` RGB, stereo depth, and YOLOv6 Nano spatial detections
- `Output:` `Combined View` and `Detections`
- `Models:` platform-specific YOLOv6 Nano descriptors in [depthai_models/](depthai_models/)
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [main.py](main.py): full device pipeline, sync strategy, and topic publication
- [utils/host_rgb_conference_node.py](utils/host_rgb_conference_node.py): host-side composed frame rendering
- [utils/host_bird_eye_view.py](utils/host_bird_eye_view.py): bird's-eye inset generation
- [utils/texts.py](utils/texts.py): visual text helpers used by the composed output
- [utils/arguments.py](utils/arguments.py): CLI surface
- [oakapp.toml](oakapp.toml): standalone packaging path

## Architecture

- `CAM_A` provides RGB frames for preview and spatial detection.
- `CAM_B` and `CAM_C` feed `StereoDepth`.
- A `SpatialDetectionNetwork` consumes RGB and stereo depth.
- An on-device `Sync` node keeps color, depth, and detections aligned before they reach host nodes.
- [utils/host_bird_eye_view.py](utils/host_bird_eye_view.py) converts spatial coordinates into a top-down inset.
- [utils/host_rgb_conference_node.py](utils/host_rgb_conference_node.py) merges RGB, colorized depth, the bird's-eye view, annotations, and logo art into one final frame.

## Data Flow

- `CAM_A + StereoDepth -> SpatialDetectionNetwork -> spatial detections`
- `color + depth + detections -> Sync -> MessageDemux`
- `detections -> BirdsEyeView host node -> bird's-eye inset`
- `color + depth + bird's-eye + detections -> CombineOutputs host node -> Combined View + Detections`

## Modification Guide

- `Safe to change:` topic names, depth colormap styling, logo usage, label rendering, bird's-eye scaling constants
- `Requires care:` fixed camera sockets, sync semantics, flipped-coordinate annotation math, spatial coordinate assumptions in the bird's-eye overlay
- `Likely to break if changed blindly:` removing on-device sync, moving away from stereo-capable devices, changing the detection label map contract

## Common Adaptations

- `To change the detector:` swap the YAML-backed model in [depthai_models/](depthai_models/) and keep the same spatial pipeline shape
- `To reuse only the composed renderer:` keep [utils/host_rgb_conference_node.py](utils/host_rgb_conference_node.py) and feed it your own synced color, depth, and detections
- `To reuse only the bird's-eye view:` keep [utils/host_bird_eye_view.py](utils/host_bird_eye_view.py) and replace the combined-frame host node
- `To build a less fixed spatial app:` compare against [neural-networks/object-detection/spatial-detections](https://github.com/luxonis/oak-examples/tree/main/neural-networks/object-detection/spatial-detections)

## Constraints

- The code assumes `CAM_A`, `CAM_B`, and `CAM_C` are the correct sockets.
- This example requires stereo hardware and stored calibration.
- `cam.initialControl.setManualFocus(130)` is hardcoded for the RGB camera.
- The host-side output is intentionally presentation-shaped rather than a generic reusable UI.

## Non-Obvious Repo Conventions

- The sync step is explicitly forced to run on-device to avoid losing aligned messages over low-bandwidth links.
- The combined frame is mirrored before annotation logic is applied, so bounding-box coordinate handling is intentionally inverted in [utils/host_rgb_conference_node.py](utils/host_rgb_conference_node.py).
- [utils/arguments.py](utils/arguments.py) still contains a generic copied description that does not describe this example accurately.
- The demo publishes only the composed outputs, not the raw intermediate topics.

## Related Examples

- [apps/default-app](https://github.com/luxonis/oak-examples/tree/main/apps/default-app): use this when you want a simpler packaged baseline
- [neural-networks/object-detection/spatial-detections](https://github.com/luxonis/oak-examples/tree/main/neural-networks/object-detection/spatial-detections): use this when you need the spatial detection scaffold more than the polished composed output
- [tutorials/camera-stereo-depth](https://github.com/luxonis/oak-examples/tree/main/tutorials/camera-stereo-depth): use this when you need a simpler stereo baseline
- [depth-measurement/calc-spatial-on-host](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/calc-spatial-on-host): use this when host-side spatial measurement matters more than presentation

## Validation

- `Run:` `python3 main.py`
- `Standalone run:` `oakctl app run .`
- `Success looks like:` the Visualizer shows `Combined View` and `Detections`, with RGB, depth, labels, and the bird's-eye inset aligned in one output
- `Common failure meaning:` the device lacks the required camera sockets, stereo calibration is unavailable, or the spatial model/runtime setup failed
