# AGENTS.md

## Summary

This example is the best RVC4 reference for preserving detail when the target object is small in the frame. It compares three strategies side-by-side: naive low-resolution face detection, two-stage person-then-face detection on high-resolution crops, and brute-force tiling over the high-resolution image.

## Use This Example When

- You need a two-stage detector pipeline that crops from a higher-resolution source.
- You want a reference for comparing naive inference against crop-based or tiling-based approaches.
- You need custom host nodes for selecting detections, switching outputs, and merging tiled results.
- You want a standalone-only RVC4 pipeline that stays close to the default Visualizer runtime.

## Do Not Use This Example When

- You need host/peripheral support on RVC2.
- You need a finished custom frontend as the primary runtime path.
- You need generic object detection rather than a detail-preserving face pipeline comparison.
- You need a minimal example without multiple branches and custom host nodes.

## Quick Facts

- `Category:` `apps/focused-vision`
- `Shape:` `frontend`
- `Primary task:` detail-preserving face detection via high-res cropping and tiling
- `Entrypoint:` [backend/src/main.py](backend/src/main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` static frontend packaged from [frontend/src/App.tsx](frontend/src/App.tsx)
- `Runs on:` RVC4 standalone only
- `Requires:` RVC4 device with RGB camera; high-resolution RGB throughput; bundled models in [backend/src/depthai_models/](backend/src/depthai_models/)
- `Input:` one RGB camera stream split into high-resolution and low-resolution branches
- `Output:` `640x640 RGB`, `NN detections`, `Non-Focus Head Crops`, `Focused Vision Head Crops`, and `Focused with Tiling`
- `Models:` [scrfd-person-detection.yaml](backend/src/depthai_models/scrfd-person-detection.yaml) and [yunet.yaml](backend/src/depthai_models/yunet.yaml)
- `Visualizer / UI:` packaged custom frontend backed by default DepthAI Visualizer topics

## Read First

- [backend/src/main.py](backend/src/main.py): all three comparison branches and published topics
- [backend/src/pipeline_builders.py](backend/src/pipeline_builders.py): RGB split, cropper, and encoder helper builders
- [backend/src/host_nodes/pick_largest_bbox.py](backend/src/host_nodes/pick_largest_bbox.py): largest-detection selection
- [backend/src/host_nodes/face_detection_from_gathered_data.py](backend/src/host_nodes/face_detection_from_gathered_data.py): 2-stage detection remapping logic
- [backend/src/host_nodes/merge_img_detections.py](backend/src/host_nodes/merge_img_detections.py): tiled detection merging
- [backend/src/arguments.py](backend/src/arguments.py): CLI arguments
- [frontend/src/App.tsx](frontend/src/App.tsx): intended comparison UI layout
- [frontend/src/constants.ts](frontend/src/constants.ts): topic-group assumptions in the frontend source
- [oakapp.toml](oakapp.toml): standalone runtime path and packaged static frontend build

## Architecture

- The backend builds one RGB camera source and splits it into high-resolution and low-resolution outputs.
- The naive branch runs face detection directly on low-resolution RGB and crops the largest detected face.
- The 2-stage branch runs person detection, crops a high-resolution person region, remaps coordinates, then runs face detection on that crop.
- The tiling branch slices the high-resolution image into overlapping tiles, runs face detection on each tile, merges detections, and crops the largest face result.
- Custom host nodes provide black fallback frames when no detections exist so the comparison layout remains stable.

## Data Flow

- `RGB low-res -> face detector -> largest bbox -> cropper -> Non-Focus Head Crops`
- `RGB low-res -> person detector -> crop high-res person -> face detector -> remap -> cropper -> Focused Vision Head Crops`
- `RGB high-res -> Tiling -> per-tile face detector -> merge + filter -> cropper -> Focused with Tiling`
- `RGB low-res -> H264 encoder -> 640x640 RGB`

## Modification Guide

- `Safe to change:` topic names, crop padding, confidence thresholds, tile overlap, comparison labels
- `Requires care:` high-res versus low-res output sizes, coordinate remapping, tile merge behavior, host-node fallback behavior
- `Likely to break if changed blindly:` the three-branch comparison symmetry, output topic names expected by the frontend source, and tile count versus throughput assumptions

## Common Adaptations

- `To change the person or face detector:` swap the model YAMLs under [backend/src/depthai_models/](backend/src/depthai_models/) and keep the same branch structure
- `To reuse only the 2-stage path:` keep the person-detection, crop, remap, and face-detection pieces from [backend/src/main.py](backend/src/main.py)
- `To experiment with higher or lower throughput:` adjust `HIGH_RES_*`, `LOW_RES_*`, and `--fps_limit`
- `To build a real custom UI:` start from [frontend/src/App.tsx](frontend/src/App.tsx) and keep its topic contracts aligned with the backend outputs

## Constraints

- The backend exits on RVC2; this is intentionally RVC4-only.
- The default FPS limit is forced to `13` if not provided.
- [backend/src/arguments.py](backend/src/arguments.py) defines `--media_path` and `--api_key`, but the current backend does not use either argument.
- [frontend/src/MessageInput.tsx](frontend/src/MessageInput.tsx) still references a `Custom Service` that the backend does not register.

## Non-Obvious Repo Conventions

- Although `INDEX.md` classifies this as a frontend app, most of the runtime state still flows through standard Visualizer topics rather than custom backend services.
- The branch comparison uses custom host nodes heavily, so this is not a good "minimal on-device only" reference.
- High-resolution cropping is the main idea to preserve object detail; the face detector input size stays small even when the source image is large.

## Related Examples

- [apps/qr-tiling](https://github.com/luxonis/oak-examples/tree/main/apps/qr-tiling): use this when you want a live tiling UI and runtime tile control
- [apps/dino-tracking](https://github.com/luxonis/oak-examples/tree/main/apps/dino-tracking): use this when you want another RVC4 standalone frontend-heavy app with backend state synchronization
- [tutorials/full-fov-nn](https://github.com/luxonis/oak-examples/tree/main/tutorials/full-fov-nn): use this when the main topic is field-of-view and resolution handling rather than multi-branch comparison
- [neural-networks/face-detection/head-posture-detection](https://github.com/luxonis/oak-examples/tree/main/neural-networks/face-detection/head-posture-detection): use this when the main goal is face-related inference rather than detail-preserving capture

## Validation

- `Run:` `oakctl app run .`
- `Success looks like:` the Visualizer shows the RGB preview plus three comparison outputs for naive, 2-stage, and tiling approaches
- `Common failure meaning:` the app is running on a non-RVC4 platform, the expected bundled models are missing, or the frontend topic expectations no longer match the backend outputs
