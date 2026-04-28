# AGENTS.md

## Summary

This example is the best host-processing reference for comparing device-generated stereo disparity against host-side `cv2.StereoSGBM` output. Use it when you need rectification, host-side stereo computation, or quality comparison logic rather than a pure on-device depth pipeline.

## Use This Example When

- You need a stereo depth example that performs major processing on the host.
- You want to compare classic host-side stereo matching against `StereoDepth` output.
- You need a reference for custom `dai.node.HostNode` usage in a stereo pipeline.
- You need rectified left/right frames and a quantitative similarity metric between two disparity outputs.

## Do Not Use This Example When

- You need RGB-aligned depth or point clouds as the main goal.
- You need ToF rather than stereo.
- You need a minimal on-device stereo reference without custom host nodes.
- You need a custom frontend or browser UI beyond the Visualizer.

## Quick Facts

- `Category:` `depth-measurement/stereo-on-host`
- `Shape:` `script+standalone`
- `Primary task:` host-side stereo disparity and SSIM comparison
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` stereo-capable devices with calibration; peripheral mode and RVC4 standalone packaging both exist
- `Requires:` left/right mono cameras, calibration stored on device, host-side OpenCV + scikit-image
- `Input:` mono left and mono right camera streams from `CAM_B` and `CAM_C`
- `Output:` rectified mono frames, device disparity visualization, host disparity visualization, SSIM annotation
- `Models:` none
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [main.py](main.py): overall pipeline wiring and published topics
- [utils/host_stereo_sgbm.py](utils/host_stereo_sgbm.py): host node that rectifies frames and computes `cv2.StereoSGBM` disparity
- [utils/host_ssim.py](utils/host_ssim.py): host node that compares generated and calculated disparity
- [utils/arguments.py](utils/arguments.py): CLI surface and example description
- [oakapp.toml](oakapp.toml): standalone packaging path

## Architecture

- Two mono camera nodes are bound explicitly to `CAM_B` and `CAM_C`.
- Their outputs are sent both to a custom host node and to the built-in `StereoDepth` node.
- The custom [utils/host_stereo_sgbm.py](utils/host_stereo_sgbm.py) host node rectifies the mono frames using calibration data, computes host-side disparity, and publishes intermediate debug outputs.
- The built-in `StereoDepth` node provides the device-generated disparity baseline.
- An `ApplyColormap` node converts device disparity into a visual depth stream.
- The custom [utils/host_ssim.py](utils/host_ssim.py) host node computes SSIM between the device disparity and host disparity and emits an annotation topic.

## Data Flow

- `CAM_B/CAM_C -> NV12 mono streams -> StereoSGBM host node -> rectified frames + host disparity`
- `CAM_B/CAM_C -> StereoDepth -> device disparity -> ApplyColormap -> generated depth visualization`
- `device disparity + host raw disparity -> SSIM host node -> SSIM annotation output`

## Modification Guide

- `Safe to change:` Visualizer topic names, `StereoDepth` preset choice, host-side annotation text, SSIM display behavior
- `Requires care:` camera sockets, resolution, calibration usage, host node input queue sizes, disparity scaling assumptions
- `Likely to break if changed blindly:` changing `RESOLUTION_SIZE` without understanding calibration/resolution interactions, moving away from stereo-capable devices, changing disparity bit-depth expectations in the SSIM node

## Common Adaptations

- `To change host stereo parameters:` edit `self.stereoProcessor = cv2.StereoSGBM_create(...)` in [utils/host_stereo_sgbm.py](utils/host_stereo_sgbm.py)
- `To compare a different stereo preset:` edit the `StereoDepth` configuration in [main.py](main.py)
- `To reuse only the host rectification/disparity logic:` keep [utils/host_stereo_sgbm.py](utils/host_stereo_sgbm.py) and remove the SSIM branch
- `To reuse only the comparison logic:` keep [utils/host_ssim.py](utils/host_ssim.py) and feed it your own generated and calculated disparity streams

## Constraints

- The example requires device calibration to be stored and readable.
- It assumes stereo mono cameras are available on `CAM_B` and `CAM_C`.
- It is not an RGBD example; there is no RGB alignment path here.
- SSIM calculation is intentionally host-side and is relatively slow, as noted in [utils/host_ssim.py](utils/host_ssim.py).
- The example uses custom host nodes, so it is a worse reference than pure on-device examples when the goal is minimal embedded compute.

## Non-Obvious Repo Conventions

- Presence of [oakapp.toml](oakapp.toml) adds an RVC4 standalone path; it does not exclude peripheral use on supported devices.
- The `StereoSGBM` and `SSIM` implementations are custom `dai.node.HostNode` classes, not normal built-in device nodes.
- `Depth generated` is the device-produced disparity visualization; `Depth SGBM` is the host-computed comparison output.

## Related Examples

- [../stereo-runtime-configuration](../stereo-runtime-configuration/): use this when you want runtime tuning of on-device stereo depth rather than host-side comparison
- [../calc-spatial-on-host](../calc-spatial-on-host/): use this when the host-side goal is spatial ROI measurement rather than disparity comparison
- [../3d-measurement/rgbd-pointcloud](../3d-measurement/rgbd-pointcloud/): use this when you need RGB-aligned point clouds instead of host stereo benchmarking
- [../../tutorials/camera-stereo-depth](../../tutorials/camera-stereo-depth/): use this when you need a simpler stereo depth baseline

## Validation

- `Run:` `python3 main.py`
- `Success looks like:` the Visualizer shows `Left Cam`, `Right Cam`, `Rectified Left`, `Rectified Right`, `Depth generated`, `Depth SGBM`, and `SSIM score`
- `Common failure meaning:` the device lacks stereo cameras, calibration is missing, or host dependencies for OpenCV / scikit-image are unavailable
