# AGENTS.md

## Summary

This is the host-side spatial ROI measurement reference in the repo. Use it when you want to calculate X/Y/Z coordinates on the host from stereo depth instead of using `SpatialLocationCalculator` on-device.

## Use This Example When

- You need host-owned ROI logic and host-owned spatial calculations.
- You want a small example of custom `dai.node.HostNode` usage for stereo depth.
- You need a movable ROI overlay with measured coordinates in the Visualizer.
- You want a simpler host-processing reference than the point-cloud or triangulation examples.

## Do Not Use This Example When

- You need neural detections or point-cloud output.
- You need ToF.
- You need a custom frontend or non-Visualizer UI.
- You need a production-ready ROI tool without code fixes.

## Quick Facts

- `Category:` `depth-measurement/calc-spatial-on-host`
- `Shape:` `script+standalone`
- `Primary task:` compute spatial coordinates for a host-controlled ROI using stereo depth
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` stereo-capable devices with `CAM_B` and `CAM_C`
- `Requires:` stereo mono pair, calibration, and host-side custom node support
- `Input:` stereo depth and a host-controlled ROI
- `Output:` `Disparity` plus `Spatial Calculations` overlay annotations
- `Models:` none
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md): usage notes and ROI sizing guidance
- [main.py](main.py): overall pipeline and topic registration
- [utils/measure_distance.py](utils/measure_distance.py): host-side ROI depth aggregation and XYZ calculation
- [utils/roi_control.py](utils/roi_control.py): ROI movement, resizing, and annotation overlay
- [oakapp.toml](oakapp.toml): packaging path

## Architecture

- `CAM_B` and `CAM_C` feed `StereoDepth`.
- `ApplyDepthColormap` turns disparity into a display stream.
- [utils/measure_distance.py](utils/measure_distance.py) defines:
  - `RegionOfInterest`
  - `Point2d`
  - `SpatialDistance`
  - `MeasureDistance`, a host node that computes XYZ values from the ROI
- [utils/roi_control.py](utils/roi_control.py) is a second host node that draws the ROI box and text overlay and emits ROI updates back to `MeasureDistance`.

## Data Flow

- `CAM_B/C -> StereoDepth -> depth`
- `depth -> MeasureDistance -> SpatialDistance buffer`
- `disparity -> ApplyDepthColormap -> ROIControl passthrough`
- `SpatialDistance + disparity preview -> ROIControl -> Spatial Calculations annotation`
- `ROIControl.output_roi -> MeasureDistance.roi_input`

## Modification Guide

- `Safe to change:` topic names, ROI step size, averaging method, overlay text
- `Requires care:` ROI coordinate handling, calibration/FOV math, threshold values, and buffer datatypes between the host nodes
- `Likely to break if changed blindly:` the angle-based spatial calculation in [utils/measure_distance.py](utils/measure_distance.py) or the custom buffer contract between `ROIControl` and `MeasureDistance`

## Common Adaptations

- `To change ROI aggregation:` replace `np.mean` in [utils/measure_distance.py](utils/measure_distance.py) with another reducer
- `To change valid depth bounds:` edit `_threshold_low` and `_threshold_high` in [utils/measure_distance.py](utils/measure_distance.py)
- `To reuse the ROI overlay only:` keep [utils/roi_control.py](utils/roi_control.py) and feed it your own depth measurements
- `To move back to an on-device approach:` use a different reference; this example intentionally keeps the spatial math on the host

## Constraints

- The README recommends using at least a `10x10` ROI for reasonable measurements.
- The example assumes stereo cameras on `CAM_B` and `CAM_C`.
- The host-side math depends on calibration-derived FOV and image-center assumptions.
- As currently written, [utils/roi_control.py](utils/roi_control.py) only calls `self.output_roi.send(self._roi)` inside the `f` branch, so the runtime ROI update behavior is narrower than the README implies unless that code is adjusted.

## Non-Obvious Repo Conventions

- `Spatial Calculations` is an annotation layer, not a raw data topic.
- The spatial values are calculated from the average valid depth inside the ROI, not from a single center pixel.
- The example uses two custom host nodes with custom `dai.Buffer` subclasses instead of built-in device nodes.

## Related Examples

- [depth-measurement/stereo-runtime-configuration](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/stereo-runtime-configuration): use this when you want runtime stereo tuning instead of host spatial math
- [depth-measurement/stereo-on-host](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/stereo-on-host): use this when you need host-side stereo disparity comparison
- [depth-measurement/3d-measurement/box-measurement](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/3d-measurement/box-measurement): use this when you need object-size measurement instead of manual ROI measurement
- [depth-measurement/wls-filter](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/wls-filter): use this when the host-side work should be disparity post-processing rather than ROI coordinate measurement

## Validation

- `Run:` `python3 main.py`
- `Standalone run:` `oakctl app run .`
- `Success looks like:` the Visualizer shows `Disparity` plus `Spatial Calculations`, and the overlay displays X/Y/Z values for the current ROI
- `Common failure meaning:` the device lacks a stereo pair, calibration is missing, or ROI updates are not propagating as expected
