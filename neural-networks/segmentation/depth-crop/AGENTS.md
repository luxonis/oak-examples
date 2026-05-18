# AGENTS.md

## Summary

This is the repository reference for combining segmentation with stereo depth and cropping the depth image by mask. Use it when you need segmentation-aware depth visualization rather than a plain segmentation effect.

## Use This Example When

- You need segmentation fused with stereo depth.
- You want one example that outputs segmentation, cutout, and depth views together.
- You need a packaged stereo-plus-segmentation baseline.

## Do Not Use This Example When

- You only need background blur.
- You only need a point cloud or generic stereo depth.
- You need instance segmentation with 3D measurements instead of semantic masking.

## Quick Facts

- `Category:` `neural-networks/segmentation/depth-crop`
- `Shape:` `script+standalone`
- `Primary task:` crop stereo depth by semantic segmentation mask
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [backend-run.sh](backend-run.sh) and [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` devices with `CAM_A`, `CAM_B`, and `CAM_C`; RVC2 peripheral, RVC4 peripheral, and RVC4 standalone packaging
- `Requires:` stereo depth, calibration, and DeepLabV3+ segmentation model
- `Input:` live color plus stereo pair
- `Output:` `Segmentation`, `Cutout`, and `Depth`
- `Models:` DeepLabV3+ YAMLs in [depthai_models/](depthai_models/)
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [utils/annotation_node.py](utils/annotation_node.py)
- [utils/arguments.py](utils/arguments.py)

## Architecture

- `CAM_A` provides the RGB source.
- `CAM_B/C` feed `StereoDepth`, which is aligned back to the color stream.
- The color stream is resized into the segmentation model input shape.
- [utils/annotation_node.py](utils/annotation_node.py) consumes the preview, disparity, and segmentation mask and emits three derived output frames, each encoded before visualization.

## Constraints

- The example requires three cameras and aligned stereo depth.
- Output streams are encoded views, not raw tensors.
- This is semantic segmentation plus depth masking, not object-instance-aware 3D measurement.

## Related Examples

- [neural-networks/segmentation/blur-background](https://github.com/luxonis/oak-examples/tree/main/neural-networks/segmentation/blur-background): use this when you only need segmentation-based blur
- [depth-measurement/3d-measurement/rgbd-pointcloud](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/3d-measurement/rgbd-pointcloud): use this when you need RGBD/point-cloud output instead of segmentation masking
- [depth-measurement/3d-measurement/box-measurement](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/3d-measurement/box-measurement): use this when you need 3D measurement built on a semantic/instance understanding of the scene

## Validation

- `Run:` `python3 main.py`
- `Success looks like:` the Visualizer shows `Segmentation`, `Cutout`, and `Depth`, with the depth view restricted by the segmentation mask
- `Common failure meaning:` stereo alignment is wrong, the device lacks the required camera topology, or the segmentation mask no longer matches the color/depth projection assumptions
