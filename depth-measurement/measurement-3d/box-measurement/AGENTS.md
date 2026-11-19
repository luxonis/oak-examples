# AGENTS.md

## Summary

This is the strongest reference in the repo for RGB-D box measurement with instance segmentation, `PointCloud` node output, and host-side cuboid fitting. Use it when you need an app-shaped stereo+RGB measurement pipeline rather than a generic point cloud viewer.

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

- `Category:` `depth-measurement/measurement-3d/box-measurement`
- `Shape:` `script+standalone`
- `Primary task:` estimate box dimensions from a colored point cloud plus instance segmentation
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
- [utils/arguments.py](utils/arguments.py): CLI surface
- [oakapp.toml](oakapp.toml): packaging and bundled model path

## Architecture

- `CAM_A` provides the RGB stream used for display and inference.
- `Depth` owns depth-source selection and aligns its depth output to RGB before `PointCloud`.
- `PointCloud` is configured with `setOrganized(True)` so the cloud keeps one point per pixel in frame order (invalid pixels have `z = 0`), and with `setLengthUnit(CENTIMETER)` so the cuboid fitter works and reports in centimeters without any host-side unit conversion.
- The point cloud explicitly targets `CAM_A` coordinates, matching the intrinsics used to project cuboid corners.
- A platform-specific box instance-segmentation archive is loaded from [depthai_models/](depthai_models/).
- `ImageManip` resizes RGB frames to the model input size before `ParsingNeuralNetwork`.
- The custom [utils/box_processing_node.py](utils/box_processing_node.py) threaded host node receives:
  - organized, colored point clouds from `PointCloud.outputPointCloud`
  - the original undistorted RGB frame
  - parsed detections and segmentation masks
- That host node projects the fitted cuboid back into image space and publishes two separate annotation layers.

## Data Flow

- `CAM_A -> ImageManip -> ParsingNeuralNetwork -> detections + segmentation mask`
- `Depth + RGB -> PointCloud -> Pointcloud`
- `synchronized pointcloud + RGB + detections -> BoxProcessingNode -> Box Detections + Cuboid Fit`
- `CAM_A preview -> Video Stream`

## Modification Guide

- `Safe to change:` topic names, FPS limit default, parser thresholds, projector usage, label text
- `Requires care:` camera sockets, RGB/depth alignment path, model input dimensions, calibration usage, point-cloud color assumptions, the point-cloud length unit (the `CuboidFitter` thresholds and labels assume centimeters)
- `Likely to break if changed blindly:` the organized cloud/mask pixel relationship, synchronized inputs, and transformation-derived intrinsics

## Common Adaptations

- `To swap the model:` replace the YAML/model pair in [depthai_models/](depthai_models/) and keep the same parser contract
- `To reuse only the measurement host logic:` keep [utils/box_processing_node.py](utils/box_processing_node.py) and feed it your own point cloud plus detections
- `To remove the cuboid overlay:` keep `outputANN` and drop the `outputANNCuboid` topic
- `To test alignment changes:` check the `Depth.setAlignTo` and `PointCloud` wiring in [main.py](main.py) and mask remapping in [utils/box_processing_node.py](utils/box_processing_node.py)

## Constraints

- The README explicitly calls out cuboid-fit instability and dimension jumps; this is a reference demo, not a hardened metrology pipeline.
- Active stereo quality matters a lot here, and the README notes that power quality can also affect stability.
- The script assumes `CAM_A` for RGB and `CAM_B/C` for stereo.
- Masks and organized point clouds must share the undistorted RGB pixel grid.

## Non-Obvious Repo Conventions

- [oakapp.toml](oakapp.toml) adds a standalone packaging path but does not mean the example is RVC4-only.
- `Box Detections` and `Cuboid Fit` are separate annotation topics layered over the same preview stream.
- Intrinsics are read from the current undistorted RGB transformation, because masks, detections, and cuboid overlays share that frame.
- The point cloud comes from `pcl.outputPointCloud`, not from a custom host reconstruction step. [utils/box_processing_node.py](utils/box_processing_node.py) reshapes it to the RGB frame size, which only works because the node runs in organized mode.
- The `Pointcloud` Visualizer topic therefore carries centimeters, while the Visualizer's distance controls assume millimeters.

## Related Examples

- [depth-measurement/measurement-3d/rgbd-pointcloud](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/measurement-3d/rgbd-pointcloud): use this when you need the `PointCloud` baseline without neural inference
- [depth-measurement/measurement-3d/tof-pointcloud](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/measurement-3d/tof-pointcloud): use this when the depth source should be ToF instead of stereo
- [depth-measurement/calc-spatial-on-host](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/calc-spatial-on-host): use this when you only need host-side spatial ROI measurement
- [apps/object-volume-measurement-3d](https://github.com/luxonis/oak-examples/tree/main/apps/object-volume-measurement-3d): use this when you need the more app-shaped frontend/backend volume-measurement workflow

## Validation

- `Run:` `python3 main.py`
- `Standalone run:` `oakctl app run .`
- `Success looks like:` the Visualizer shows `Video Stream`, `Box Detections`, `Cuboid Fit`, and `Pointcloud`, and detected boxes receive dimension labels when the fit succeeds
- `Common failure meaning:` stereo alignment is poor, the device lacks the expected camera topology, the model bundle is unavailable, or the cuboid fit is failing on noisy depth
