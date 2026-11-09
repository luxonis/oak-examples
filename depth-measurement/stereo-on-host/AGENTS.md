# AGENTS.md

## Summary

Host-side stereo benchmark example. It compares device `StereoDepth` disparity against host-computed `cv2.StereoSGBM` disparity, including rectified mono previews and an SSIM annotation.

## Use This Example When

- You need calibrated rectified stereo inputs with `cv2.StereoSGBM` logic.
- You want to compare host stereo matching against device `StereoDepth` output.
- You need a concrete custom `dai.node.HostNode` reference in a stereo pipeline.
- You need rectified left/right streams plus a quantitative disparity comparison.

## Do Not Use This Example When

- You need a minimal on-device stereo depth baseline.
- You need RGB-aligned depth, RGBD, or point clouds.
- You need ToF, a custom frontend, ROS, C++, or multi-device logic.

## Quick Facts

- `Entrypoint:` [main.py](main.py)
- `Host stereo node:` [utils/host_stereo_sgbm.py](utils/host_stereo_sgbm.py)
- `SSIM node:` [utils/host_ssim.py](utils/host_ssim.py)
- `Standalone config:` [oakapp.toml](oakapp.toml)
- `Input:` mono camera streams from `CAM_B` and `CAM_C`
- `Output:` rectified mono frames, device disparity visualization, host disparity visualization, SSIM annotation
- `Models:` none

## Read First

- [main.py](main.py): camera sockets, pipeline wiring, stereo configuration, and published topics
- [utils/host_stereo_sgbm.py](utils/host_stereo_sgbm.py): rectified-frame matching and `cv2.StereoSGBM_create(...)`
- [utils/host_ssim.py](utils/host_ssim.py): disparity normalization and SSIM annotation output
- [utils/arguments.py](utils/arguments.py): CLI surface

## Architecture

- [main.py](main.py) binds the two mono cameras explicitly to `CAM_B` and `CAM_C`.
- The mono outputs feed `StereoDepth`, with calibrated translation, distortion correction and rectified-left alignment explicitly enabled. Its `rectifiedLeft`/`rectifiedRight` feed the host matcher, so both matchers share one geometry.
- `StereoSGBM` accepts timestamp-matched grayscale rectified frames (within 5 ms), computes host disparity, and preserves left-frame metadata. It does not rectify again.
- `StereoDepth` uses `FAST_DENSITY`, left-right check, subpixel enabled, and extended disparity disabled.
- `ApplyColormap` turns device disparity into the `Depth generated` visualization.
- `SSIM` compares device disparity with raw host disparity and emits the `SSIM score` annotation topic.

## Data Flow

- `CAM_B/CAM_C -> StereoDepth rectification -> StereoSGBM host node -> host disparity`
- `CAM_B/CAM_C -> StereoDepth -> ApplyColormap -> Depth generated`
- `StereoDepth disparity + StereoSGBM raw disparity -> SSIM host node -> SSIM score`

## Modification Guide

- `Safe to change:` Visualizer topic names, SSIM annotation text, `StereoDepth` preset/settings for experiments
- `Requires care:` camera sockets, `RESOLUTION_SIZE`, calibration usage, host-node queue sizes, disparity scaling and bit-depth assumptions
- `Likely to break if changed blindly:` using a device without `CAM_B`/`CAM_C`, changing resolution without checking calibration handling, changing disparity output types before SSIM normalization

## Common Adaptations

- `Tune host stereo:` edit `cv2.StereoSGBM_create(...)` in [utils/host_stereo_sgbm.py](utils/host_stereo_sgbm.py).
- `Compare a different device stereo setup:` edit the `StereoDepth` configuration in [main.py](main.py).
- `Reuse only host disparity:` keep [utils/host_stereo_sgbm.py](utils/host_stereo_sgbm.py) and remove the SSIM branch.
- `Reuse only comparison:` keep [utils/host_ssim.py](utils/host_ssim.py) and feed it generated/calculated disparity streams.

## Constraints

- Requires readable device calibration.
- Requires stereo mono cameras on `CAM_B` and `CAM_C`.
- Not an RGBD example; it does not align depth to RGB.
- SSIM is host-side and intentionally slower than the main stereo path. Both disparities are converted to horizontal pixel units before comparison: device subpixel scale from configuration, OpenCV scale 16. Invalid host values become zero. SSIM includes invalid/occluded areas and is a qualitative similarity score, not metric depth accuracy.

## Related Examples

- [depth-measurement/stereo-runtime-configuration](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/stereo-runtime-configuration): runtime tuning of on-device stereo depth
- [depth-measurement/calc-spatial-on-host](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/calc-spatial-on-host): host-side spatial ROI measurement
- [depth-measurement/measurement-3d/rgbd-pointcloud](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/measurement-3d/rgbd-pointcloud): RGB-aligned point clouds
- [tutorials/camera-stereo-depth](https://github.com/luxonis/oak-examples/tree/main/tutorials/camera-stereo-depth): simpler stereo depth baseline

## Validation

- `Run:` `python3 main.py`
- `Success looks like:` Visualizer shows `Left Cam`, `Right Cam`, `Rectified Left`, `Rectified Right`, `Depth generated`, `Depth SGBM`, and `SSIM score`
- `Common failure meaning:` missing stereo cameras, missing calibration, or missing host dependencies such as OpenCV/scikit-image

- Check that rectified image features lie on the same rows, and confirm all seven topics update on RVC2 and RVC4. Compare with a measured-distance scene before claiming metric accuracy.
