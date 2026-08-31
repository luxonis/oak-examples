# AGENTS.md

## Summary

This is the host-side WLS disparity post-processing reference in the repo. Use it when you want to keep stereo depth generation on-device but experiment with host-side filtering and live parameter tuning before building a more specialized disparity pipeline.

## Use This Example When

- You need a reference for OpenCV `ximgproc` WLS filtering on top of DepthAI disparity.
- You want a host-side post-processing step with interactive lambda and sigma tuning.
- You need a stereo example that publishes both raw and filtered disparity views.
- You want a lightweight host-processing reference without neural inference.

## Do Not Use This Example When

- You need ROI spatial measurement.
- You need point clouds or RGB alignment.
- You need ToF.
- You need a pure on-device stereo pipeline with no host post-processing dependency.

## Quick Facts

- `Category:` `depth-measurement/wls-filter`
- `Shape:` `script+standalone`
- `Primary task:` apply host-side WLS filtering to stereo disparity and inspect the effect live
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` stereo-capable devices with `CAM_B` and `CAM_C`
- `Requires:` stereo mono pair, calibration, and OpenCV contrib `ximgproc`
- `Input:` device disparity plus `rectifiedRight`
- `Output:` `Rectified Right`, `Disparity`, `WLS Raw Depth`, `WLS Filtered Disparity`, `WLS Colored Disparity`, and `WLS Annotations`
- `Models:` none
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md): keyboard control summary
- [main.py](main.py): pipeline setup and displayed topics
- [utils/host_wls_filter.py](utils/host_wls_filter.py): the host-side filter implementation and key handling
- [utils/arguments.py](utils/arguments.py): CLI surface
- [oakapp.toml](oakapp.toml): packaging path and extra runtime libraries

## Architecture

- `CAM_B` and `CAM_C` feed `StereoDepth`.
- The device branch publishes:
  - raw disparity
  - rectified right image
- The custom [utils/host_wls_filter.py](utils/host_wls_filter.py) host node consumes those streams, runs OpenCV WLS filtering, derives a host-side depth visualization, and emits overlay annotations for the current lambda and sigma values.
- Separate `ApplyDepthColormap` nodes colorize raw disparity and filtered disparity for display.

## Data Flow

- `CAM_B/C -> StereoDepth -> disparity + rectifiedRight`
- `disparity + rectifiedRight -> WLSFilter host node -> filtered disparity + depth visualization + annotations`
- `raw disparity -> ApplyDepthColormap -> Disparity`
- `filtered disparity -> ApplyDepthColormap -> WLS Colored Disparity`

## Modification Guide

- `Safe to change:` initial lambda/sigma defaults, topic names, color maps, stereo confidence defaults
- `Requires care:` disparity scale assumptions, baseline/FOV math, and OpenCV WLS parameter ranges
- `Likely to break if changed blindly:` the conversion from filtered disparity to host depth in [utils/host_wls_filter.py](utils/host_wls_filter.py), or the expectation that `cv2.ximgproc` is available

## Common Adaptations

- `To change the tuning range:` edit the bounds in the `Filter` class in [utils/host_wls_filter.py](utils/host_wls_filter.py)
- `To reuse only the host filter stage:` keep [utils/host_wls_filter.py](utils/host_wls_filter.py) and feed it your own disparity and right image streams
- `To compare against an unfiltered host stereo baseline:` switch to [depth-measurement/stereo-on-host](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/stereo-on-host)
- `To move from disparity cleanup into spatial measurement:` switch to [depth-measurement/calc-spatial-on-host](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/calc-spatial-on-host)

## Constraints

- This example depends on OpenCV contrib `ximgproc`, which is a stronger host dependency than the simpler stereo demos.
- `WLS Raw Depth` is a host-generated BGR visualization derived from filtered disparity, not a raw depth topic.
- The host filter currently assumes a fixed `71.86` degree FOV in [utils/host_wls_filter.py](utils/host_wls_filter.py).
- The example assumes stereo cameras on `CAM_B` and `CAM_C`.

## Non-Obvious Repo Conventions

- Lowercase `l` decreases lambda and uppercase `L` increases it; the same lowercase/uppercase pattern applies to sigma with `s` and `S`.
- `WLS Filtered Disparity` is published as raw filtered disparity, while `WLS Colored Disparity` is the separately colorized view.
- The host node converts the calibration baseline to millimeters internally before deriving depth.

## Related Examples

- [depth-measurement/stereo-on-host](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/stereo-on-host): use this when you want host-side stereo comparison instead of WLS post-processing
- [depth-measurement/stereo-runtime-configuration](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/stereo-runtime-configuration): use this when the tuning target should be device stereo parameters rather than host filters
- [depth-measurement/calc-spatial-on-host](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/calc-spatial-on-host): use this when the host-side task should become ROI coordinate measurement
- [depth-measurement/3d-measurement/rgbd-pointcloud](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/3d-measurement/rgbd-pointcloud): use this when the end goal is a point cloud rather than a filtered disparity view

## Validation

- `Run:` `python3 main.py`
- `Standalone run:` `oakctl app run .`
- `Success looks like:` the Visualizer shows raw disparity, filtered disparity, and WLS annotations, and `l/L/s/S` visibly changes the filtered output
- `Common failure meaning:` the device lacks a stereo pair, OpenCV contrib is unavailable, or the host disparity/depth assumptions no longer match the stereo configuration
