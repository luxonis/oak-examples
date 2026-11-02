# AGENTS.md

## Summary

This is the repository reference for comparing CREStereo neural stereo matching against calibrated DepthAI stereo depth. Use it when you need a neural stereo model and a `dai.node.StereoDepth` baseline in the same visualizer session.

## Use This Example When

- You need a neural stereo depth reference.
- You want to compare CREStereo-derived depth against DepthAI `Depth` output.
- You need the supported CREStereo model variants and platform restrictions documented in one place.

## Do Not Use This Example When

- You need host-side stereo benchmarking with external models.
- You need RGBD point clouds or spatial detections.
- You need depth from a monocular model.

## Quick Facts

- `Category:` `neural-networks/depth-estimation/crestereo-depth-matching`
- `Shape:` `script+standalone`
- `Primary task:` compare CREStereo-derived depth with classical stereo depth
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` stereo-capable RVC2 and RVC4 devices with platform-specific supported model variants
- `Requires:` `CAM_B/C` stereo pair and supported CREStereo model slug for the platform
- `Input:` stereo camera pair only
- `Output:` `Depth`, `CREStereo Depth`, `Rectified Left`, `Rectified Right`
- `Models:` default CREStereo YAMLs in [depthai_models/](depthai_models/)
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [utils/arguments.py](utils/arguments.py)
- [oakapp.toml](oakapp.toml)

## Architecture

- Stereo mono cameras on `CAM_B` and `CAM_C` feed `StereoDepth` with distortion correction, calibrated translation and rectified-left alignment. Its rectified outputs also feed CREStereo, making both matchers use the same geometry.
- The classical baseline explicitly uses `StereoDepth`, rather than `Depth.AUTO`, to keep this a comparison of matching algorithms on the same input pair.
- A host `RectifiedColor` node replicates rectified mono into the model color format. `Sync` (5 ms, indefinite attempts) and `MessageDemux` provide paired inputs for CREStereo.
- The neural path uses `ParsingNeuralNetwork`; RVC4 explicitly sets the `snpe` DSP backend.
- [utils/disparity_to_depth.py](utils/disparity_to_depth.py) converts CREStereo disparity to depth using the calibrated baseline and actual rectified-left inference passthrough intrinsics before visualization. It checks matching sequences and output dimensions; non-finite, negative and near-zero disparities become invalid (zero depth). Output is RAW16 millimeters.
- `ApplyDepthColormap` visualizes both metric-depth outputs side by side.

## Constraints

- `RectifiedColor` runs on the host because RVC4 `ImageManip` cannot convert StereoDepth RAW8 to the model color format. This adds a host round trip, while retaining geometry and metadata.

- Supported model slugs are hardcoded by platform in [main.py](main.py).
- There is no media replay path; this example is stereo-camera only.
- Default FPS is intentionally low, especially on RVC2.

## Related Examples

- [neural-networks/depth-estimation/foundation-stereo](https://github.com/luxonis/oak-examples/tree/main/neural-networks/depth-estimation/foundation-stereo): use this when you need a heavier host-run stereo model baseline
- [neural-networks/depth-estimation/neural-depth](https://github.com/luxonis/oak-examples/tree/main/neural-networks/depth-estimation/neural-depth): use this when you need Luxonis NeuralDepth on RVC4
- [depth-measurement/stereo-on-host](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/stereo-on-host): use this when you want host-side stereo comparison rather than on-device neural disparity

## Validation

- `Run:` `python3 main.py`
- `Success looks like:` the Visualizer shows `Depth` and `CREStereo Depth`, and both streams update from the stereo pair
- `Common failure meaning:` the chosen model is unsupported for the platform, the device lacks stereo cameras, or the requested FPS/model size is too heavy for the hardware

- Confirm both metric-depth streams and rectified previews update. Inspect vertical residuals and validate scale against known distances and off-axis points before claiming accuracy. The model must emit horizontal disparity in input-pixel units at the input resolution.
