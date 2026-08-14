# AGENTS.md

## Summary

This is the strongest reference in the repo for RGBD box measurement with instance segmentation, point clouds, and host-side cuboid fitting. Use it when you need an app-shaped stereo+RGB measurement pipeline rather than a generic point cloud viewer.

## Use This Example When

- You need a reference for measuring object dimensions from RGB-aligned depth.
- You want a custom host node that consumes a point cloud plus neural detections.
- You need a segmentation-driven cuboid fit rather than a plain disparity or ROI demo.
- You want a packaged example with a model bundle and standalone packaging path.

## Do Not Use This Example When

- You need a minimal point cloud baseline without neural inference.
- You need a ToF-specific tuning example rather than unified depth.
- You need a browser frontend or backend/frontend service split.
- You need production-grade stable metrology without cuboid-fit jitter.

## Quick Facts

- `Category:` `depth-measurement/3d-measurement/box-measurement`
- `Shape:` `script+standalone`
- `Primary task:` estimate box dimensions from RGBD plus instance segmentation
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` stereo-capable RGB devices with `CAM_A`, `CAM_B`, and `CAM_C`; best treated as a peripheral-mode reference, with packaging files also present
- `Requires:` active stereo, stored calibration, RGB camera, mono stereo pair, model download support
- `Input:` RGB frames from `CAM_A`, depth from `CAM_B/C`, and a platform-specific box instance-segmentation model
- `Output:` `Video Stream`, `Box Detections`, `Cuboid Fit`, and `Pointcloud`
- `Models:` `box_instance_segmentation.<platform>.yaml` in [depthai_models/](depthai_models/)
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md): usage notes and accuracy caveats
- [main.py](main.py): pipeline wiring, platform branching, and Visualizer topics
- [utils/box_processing_node.py](utils/box_processing_node.py): host-side mask rendering, point-cloud filtering, and cuboid-fit annotations
- [utils/cuboid_fitter.py](utils/cuboid_fitter.py): fitting logic used to estimate dimensions
- [utils/helper_functions.py](utils/helper_functions.py): intrinsics readout plus mask resize/pad helpers
- [utils/arguments.py](utils/arguments.py): CLI surface
- [oakapp.toml](oakapp.toml): packaging and bundled model path

## Architecture

- `CAM_A` provides the RGB stream used for display and inference.
- `Depth` owns depth-source selection and aligns its depth output to RGB before `RGBD`.
- A platform-specific box instance-segmentation archive is loaded from [depthai_models/](depthai_models/).
- `ImageManip` resizes RGB frames to the model input size before `ParsingNeuralNetwork`.
- The custom [utils/box_processing_node.py](utils/box_processing_node.py) threaded host node receives:
  - RGBD point clouds
  - the NN passthrough RGB frame
  - parsed detections and segmentation masks
- That host node projects the fitted cuboid back into image space and publishes two separate annotation layers.

## Data Flow

- `CAM_A -> ImageManip -> ParsingNeuralNetwork -> detections + segmentation mask`
- `Depth -> RGBD -> Pointcloud`
- `pointcloud + NN passthrough + detections -> BoxProcessingNode -> Box Detections + Cuboid Fit`
- `CAM_A preview -> Video Stream`

## Modification Guide

- `Safe to change:` topic names, FPS limit default, parser thresholds, projector usage, label text
- `Requires care:` camera sockets, RGB/depth alignment path, model input dimensions, calibration usage, point-cloud color assumptions
- `Likely to break if changed blindly:` the fixed `640x400` and `512x320` assumptions in [utils/box_processing_node.py](utils/box_processing_node.py), intrinsics scaling, and mask reprojection logic

## Common Adaptations

- `To swap the model:` replace the YAML/model pair in [depthai_models/](depthai_models/) and keep the same parser contract
- `To reuse only the measurement host logic:` keep [utils/box_processing_node.py](utils/box_processing_node.py) and feed it your own point cloud plus detections
- `To remove the cuboid overlay:` keep `outputANN` and drop the `outputANNCuboid` topic
- `To test alignment changes:` start from the `RGBD` and `ImageAlign` branch in [main.py](main.py)

## Constraints

- The README explicitly calls out cuboid-fit instability and dimension jumps; this is a reference demo, not a hardened metrology pipeline.
- Active stereo quality matters a lot here, and the README notes that power quality can also affect stability.
- The script assumes `CAM_A` for RGB and `CAM_B/C` for stereo.
- [utils/box_processing_node.py](utils/box_processing_node.py) hardcodes `IMG_WIDTH=640`, `IMG_HEIGHT=400`, `NN_WIDTH=512`, and `NN_HEIGHT=320`.
- RVC2 disables the median filter path, so stereo behavior differs by platform.

## Non-Obvious Repo Conventions

- [oakapp.toml](oakapp.toml) adds a standalone packaging path but does not mean the example is RVC4-only.
- `Box Detections` and `Cuboid Fit` are separate annotation topics layered over the same preview stream.
- Intrinsics are read for `CAM_A` at NN resolution, because the cuboid overlay is projected into model-space image coordinates.
- The point cloud comes from `rgbd.pcl`, not from a custom host reconstruction step.

## Related Examples

- [depth-measurement/3d-measurement/rgbd-pointcloud](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/3d-measurement/rgbd-pointcloud): use this when you need the RGBD + point-cloud baseline without neural inference
- [depth-measurement/3d-measurement/tof-pointcloud](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/3d-measurement/tof-pointcloud): use this when the depth source should be ToF instead of stereo
- [depth-measurement/calc-spatial-on-host](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/calc-spatial-on-host): use this when you only need host-side spatial ROI measurement
- [apps/object-volume-measurement-3d](https://github.com/luxonis/oak-examples/tree/main/apps/object-volume-measurement-3d): use this when you need the more app-shaped frontend/backend volume-measurement workflow

## Validation

- `Run:` `python3 main.py`
- `Standalone run:` `oakctl app run .`
- `Success looks like:` the Visualizer shows `Video Stream`, `Box Detections`, `Cuboid Fit`, and `Pointcloud`, and detected boxes receive dimension labels when the fit succeeds
- `Common failure meaning:` stereo alignment is poor, the device lacks the expected camera topology, the model bundle is unavailable, or the cuboid fit is failing on noisy depth
